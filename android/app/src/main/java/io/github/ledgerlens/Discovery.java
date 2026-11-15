package io.github.ledgerlens;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.HttpURLConnection;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.InterfaceAddress;
import java.net.NetworkInterface;
import java.net.Socket;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/**
 * 只凭配对码在局域网里找到电脑，不用手填地址。
 * 1) 先发 UDP 广播 “LEDGERLENS?”，电脑端回答自己的端口；
 * 2) 广播被路由器挡掉时，逐个扫描本网段（x.x.x.1 ~ 254）的同步端口；
 * 3) 对找到的每台电脑用配对码请求 /api/pair，验证通过的那台就是要连的。
 * 配对码只发给已确认运行着流水分析助手的地址。
 */
final class Discovery {
    static final int UDP_PORT = 8755;
    static final int[] HTTP_PORTS = {8756, 8757, 8758};

    private Discovery() {
    }

    /** 返回 {电脑地址, 错误}。成功时错误为 null；失败时地址为 null，错误是 none / code / locked。 */
    static String[] find(String code) {
        Set<String> hosts = new LinkedHashSet<>(broadcast());
        if (hosts.isEmpty()) hosts.addAll(scan());
        if (hosts.isEmpty()) return new String[]{null, "none"};
        String err = "code";
        for (String h : hosts) {
            int status = pair(h, code);
            if (status == 200) return new String[]{h, null};
            if (status == 429) err = "locked";
        }
        return new String[]{null, err};
    }

    private static List<String> broadcast() {
        List<String> found = new ArrayList<>();
        try (DatagramSocket s = new DatagramSocket()) {
            s.setBroadcast(true);
            s.setSoTimeout(350);
            byte[] q = "LEDGERLENS?".getBytes(StandardCharsets.UTF_8);
            Set<InetAddress> targets = new LinkedHashSet<>();
            targets.add(InetAddress.getByName("255.255.255.255"));
            for (InterfaceAddress ia : addresses()) if (ia.getBroadcast() != null) targets.add(ia.getBroadcast());
            long end = System.currentTimeMillis() + 1800;
            int round = 0;
            while (System.currentTimeMillis() < end) {
                if (round++ % 3 == 0) {
                    for (InetAddress t : targets) {
                        try {
                            s.send(new DatagramPacket(q, q.length, t, UDP_PORT));
                        } catch (Exception ignored) {
                        }
                    }
                }
                try {
                    byte[] buf = new byte[512];
                    DatagramPacket p = new DatagramPacket(buf, buf.length);
                    s.receive(p);
                    JSONObject o = new JSONObject(new String(buf, 0, p.getLength(), StandardCharsets.UTF_8));
                    if ("ledger-lens".equals(o.optString("app"))) {
                        String h = "http://" + p.getAddress().getHostAddress() + ":" + o.optInt("port", HTTP_PORTS[0]);
                        if (!found.contains(h)) found.add(h);
                    }
                } catch (Exception ignored) {
                }
                if (!found.isEmpty() && System.currentTimeMillis() > end - 1200) break;
            }
        } catch (Exception ignored) {
        }
        return found;
    }

    private static List<String> scan() {
        final List<String> found = Collections.synchronizedList(new ArrayList<String>());
        ExecutorService pool = Executors.newFixedThreadPool(48);
        for (InterfaceAddress ia : addresses()) {
            byte[] a = ia.getAddress().getAddress();
            final String base = (a[0] & 255) + "." + (a[1] & 255) + "." + (a[2] & 255) + ".";
            final int self = a[3] & 255;
            for (int i = 1; i < 255; i++) {
                if (i == self) continue;
                final String ip = base + i;
                pool.execute(new Runnable() {
                    @Override
                    public void run() {
                        for (int port : HTTP_PORTS) {
                            if (!open(ip, port)) continue;
                            String h = "http://" + ip + ":" + port;
                            String[] r = get(h + "/api/ping", null);
                            if (r[1] != null && r[1].contains("ledger-lens")) {
                                found.add(h);
                                return;
                            }
                        }
                    }
                });
            }
        }
        pool.shutdown();
        try {
            pool.awaitTermination(15, TimeUnit.SECONDS);
        } catch (InterruptedException ignored) {
        }
        pool.shutdownNow();
        return new ArrayList<>(found);
    }

    /** 本机所有非回环的局域网 IPv4 地址（Wi-Fi、热点等）。 */
    private static List<InterfaceAddress> addresses() {
        List<InterfaceAddress> out = new ArrayList<>();
        try {
            for (NetworkInterface ni : Collections.list(NetworkInterface.getNetworkInterfaces())) {
                if (!ni.isUp() || ni.isLoopback()) continue;
                for (InterfaceAddress ia : ni.getInterfaceAddresses()) {
                    if (ia.getAddress() instanceof Inet4Address && ia.getAddress().isSiteLocalAddress()) out.add(ia);
                }
            }
        } catch (Exception ignored) {
        }
        return out;
    }

    private static boolean open(String ip, int port) {
        try (Socket s = new Socket()) {
            s.connect(new InetSocketAddress(ip, port), 350);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    private static int pair(String host, String code) {
        String[] r = get(host + "/api/pair", code);
        try {
            return Integer.parseInt(r[0]);
        } catch (Exception e) {
            return 0;
        }
    }

    /** 返回 {HTTP 状态码, 正文}；连不上时都是 null。 */
    private static String[] get(String url, String token) {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(url).openConnection();
            c.setConnectTimeout(1500);
            c.setReadTimeout(2500);
            if (token != null) c.setRequestProperty("X-Token", token);
            int status = c.getResponseCode();
            InputStream in = status >= 400 ? c.getErrorStream() : c.getInputStream();
            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            if (in != null) {
                byte[] buf = new byte[1024];
                int n;
                while ((n = in.read(buf)) > 0 && bo.size() < 8192) bo.write(buf, 0, n);
                in.close();
            }
            return new String[]{String.valueOf(status), new String(bo.toByteArray(), StandardCharsets.UTF_8)};
        } catch (Exception e) {
            return new String[]{null, null};
        } finally {
            if (c != null) c.disconnect();
        }
    }
}
