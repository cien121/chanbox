# RelayBox

个人自用的 Android 代理客户端，基于 sing-box 核心。

> 仅供个人学习使用。

## 功能

- **多协议支持**：Hysteria2（含跳跃端口、ECH）、VLESS、VMess、Trojan、Shadowsocks、AnyTLS
- **XHTTP 传输**：支持 Xray XHTTP（packet-up / stream-up / stream-one 模式）
- **负载均衡**：urltest 自动测速，流量走最快节点
- **真连接测试**：一键测延迟、测速（Speedtest.net）
- **路由规则**：广告拦截、国内外分流

## 构建

```bash
# 需要 Android SDK + NDK
./gradlew assembleRelease
```

或走 GitHub Actions 云编译（`.github/workflows/build.yml`），产物为 arm64-v8a APK。

## 技术栈

- sing-box (Leadaxe fork, 含 XHTTP 支持)
- Kotlin / Jetpack Compose
- Xray-core 桥接（实验性）

##  License

Apache-2.0
