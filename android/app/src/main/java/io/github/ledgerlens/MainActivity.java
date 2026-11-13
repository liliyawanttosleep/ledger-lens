package io.github.ledgerlens;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/**
 * 流水分析助手 · 安卓端。
 * 界面是打包在 assets/www 里的网页（与电脑端提供给手机浏览器的是同一份），
 * 数据通过局域网从电脑同步后保存在本机，离线也能查看。
 */
public class MainActivity extends Activity {
    private static final String HOME = "file:///android_asset/www/index.html";
    private WebView web;

    @SuppressLint("SetJavaScriptEnabled")
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
        setContentView(web);
        if (savedInstanceState != null) {
            web.restoreState(savedInstanceState);
        } else {
            web.loadUrl(HOME + pairingHash(getIntent()));
        }
    }

    /** 从“在 App 中打开”的深链里取出电脑地址和配对码，交给网页处理。 */
    private String pairingHash(Intent intent) {
        Uri d = intent == null ? null : intent.getData();
        if (d == null || !"ledgerlens".equals(d.getScheme())) return "";
        String h = d.getQueryParameter("h"), t = d.getQueryParameter("t");
        if (h == null || t == null) return "";
        return "#pair=" + Uri.encode(h) + "&t=" + Uri.encode(t);
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
