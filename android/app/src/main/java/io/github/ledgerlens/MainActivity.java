package io.github.ledgerlens;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import com.google.zxing.integration.android.IntentIntegrator;
import com.google.zxing.integration.android.IntentResult;

import org.json.JSONObject;

/**
 * 流水分析助手 · 安卓端。
 * 界面是打包在 assets/www 里的网页（与电脑端提供给手机浏览器的是同一份），
 * 数据通过局域网从电脑同步后保存在本机，离线也能查看。
 *
 * 配对有三种入口，最后都落到网页里的 window.onPairNative(电脑地址, 配对码)：
 *   1. App 内扫电脑上的二维码（LedgerNative.scan）
 *   2. 只输入 8 位配对码，由 Discovery 在局域网里找到电脑（LedgerNative.discover）
 *   3. 浏览器里点“在 App 中打开”的深链 ledgerlens://pair?h=…&t=…
 */
public class MainActivity extends Activity {
    private static final String HOME = "file:///android_asset/www/index.html";
    private WebView web;

    @SuppressLint({"SetJavaScriptEnabled", "AddJavascriptInterface"})
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);          // 同步来的数据存在 localStorage
        s.setAllowFileAccess(true);
        s.setAllowUniversalAccessFromFileURLs(true);  // 允许本地页面请求电脑端的同步接口
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        s.setTextZoom(100);
        web.setWebViewClient(new WebViewClient());
        web.setWebChromeClient(new WebChromeClient());  // 让 confirm() 等对话框可用
        web.setOverScrollMode(WebView.OVER_SCROLL_NEVER);
        web.addJavascriptInterface(new Bridge(), "LedgerNative");  // 只加载打包在 App 里的页面，不打开外部网页
        setContentView(web);
        if (savedInstanceState != null) {
            web.restoreState(savedInstanceState);
        } else {
            web.loadUrl(HOME + pairingHash(getIntent()));
        }
    }

    /** 网页能调用的原生能力。 */
    private final class Bridge {
        /** 只凭配对码在局域网里找电脑；结果回调 window.onDiscover(地址或 null, 错误或 null)。 */
        @JavascriptInterface
        public void discover(final String code) {
            new Thread(new Runnable() {
                @Override
                public void run() {
                    String[] r = Discovery.find(code == null ? "" : code.trim().toUpperCase());
                    js("window.onDiscover&&window.onDiscover(" + quote(r[0]) + "," + quote(r[1]) + ")");
                }
            }).start();
        }

        /** 打开相机扫电脑上的二维码。 */
        @JavascriptInterface
        public void scan() {
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    IntentIntegrator i = new IntentIntegrator(MainActivity.this);
                    i.setDesiredBarcodeFormats(IntentIntegrator.QR_CODE);
                    i.setBeepEnabled(false);
                    i.setOrientationLocked(true);
                    i.setPrompt(getString(R.string.scan_prompt));
                    i.initiateScan();
                }
            });
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        IntentResult r = IntentIntegrator.parseActivityResult(requestCode, resultCode, data);
        if (r == null) {
            super.onActivityResult(requestCode, resultCode, data);
            return;
        }
        if (r.getContents() == null) return;  // 用户取消了
        String[] p = parsePairing(r.getContents());
        if (p == null) js("window.onScanFail&&window.onScanFail()");
        else js("window.onPairNative&&window.onPairNative(" + quote(p[0]) + "," + quote(p[1]) + ")");
    }

    /**
     * 二维码 / 深链里的配对信息 → {电脑地址, 配对码}。
     * 二维码是 http://电脑地址:端口/?t=配对码；深链是 ledgerlens://pair?h=http://电脑地址:端口&t=配对码。
     */
    private static String[] parsePairing(String text) {
        try {
            Uri u = Uri.parse(text.trim());
            String t = u.getQueryParameter("t");
            if (t == null || t.isEmpty()) return null;
            if ("ledgerlens".equals(u.getScheme())) {
                String h = u.getQueryParameter("h");
                return h == null || h.isEmpty() ? null : new String[]{h, t};
            }
            if ("http".equals(u.getScheme()) && u.getHost() != null) {
                return new String[]{"http://" + u.getHost() + (u.getPort() > 0 ? ":" + u.getPort() : ""), t};
            }
        } catch (Exception ignored) {
        }
        return null;
    }

    private void js(final String code) {
        web.post(new Runnable() {
            @Override
            public void run() {
                web.evaluateJavascript(code, null);
            }
        });
    }

    private static String quote(String s) {
        return s == null ? "null" : JSONObject.quote(s);
    }

    /** 从“在 App 中打开”的深链里取出电脑地址和配对码，交给网页处理。 */
    private String pairingHash(Intent intent) {
        Uri d = intent == null ? null : intent.getData();
        String[] p = d == null ? null : parsePairing(d.toString());
        if (p == null) return "";
        return "#pair=" + Uri.encode(p[0]) + "&t=" + Uri.encode(p[1]);
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        String hash = pairingHash(intent);
        if (!hash.isEmpty()) web.loadUrl(HOME + hash);
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        web.saveState(outState);
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack(); else super.onBackPressed();
    }
}
