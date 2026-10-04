// Package xraybridge — Xray-core 桥接，用于 ChanBox 支持 xhttp 和 REALITY。
//
// 背景：NekoBox 的 sing-box 核心不支持 xhttp 传输（transport/v2rayhttp 是
// 传统 V2Ray HTTP，不是 Xray 的 XHTTP/splithttp）。Xray 26.9.9+ 的 REALITY
// 服务端要求 X25519MLKEM768 后量子握手，sing-box 发不出。
// 本包把 xray-core 作为 Go 库嵌入，通过 gomobile 打进同一个 libcore.aar，
// 为每个 xhttp/REALITY 节点起一个进程内 Xray 实例，暴露本地 SOCKS5（含 UDP），
// sing-box 通过 socks outbound 连接它。
//
// 参考实现：Multik-Sila 的 mobile/silaxray/bridge.go（已验证可用）。
// gomobile 绑定限制：只暴露 string/int/error 等简单类型。
package xraybridge

import (
	"bytes"
	"fmt"
	"sync"

	core "github.com/xtls/xray-core/core"
	"github.com/xtls/xray-core/infra/conf/serial"

	// 注册所有协议和传输（含 xhttp）。Xray 通过全局注册表在 init() 时
	// 组装实现，缺了这个 import 配置能解析但跑不起来。
	_ "github.com/xtls/xray-core/main/distro/all"
)

// Bridge 是一个运行中的 Xray 实例。由 Kotlin 侧持有，显式关闭。
type Bridge struct {
	mu      sync.Mutex
	server  *core.Instance
	running bool
	port    int
}

// Start 用 Xray JSON 配置启动一个桥接实例。
// configJSON 与 Xray 原生配置格式一致（inbound 为 127.0.0.1:port 的 SOCKS5）。
// 返回的 *Bridge 由调用方持有并在不需要时调用 Stop。
func Start(configJSON string) (*Bridge, error) {
	config, err := serial.LoadJSONConfig(bytes.NewReader([]byte(configJSON)))
	if err != nil {
		return nil, fmt.Errorf("xraybridge: 解析配置失败: %w", err)
	}
	server, err := core.New(config)
	if err != nil {
		return nil, fmt.Errorf("xraybridge: 创建实例失败: %w", err)
	}
	if err := server.Start(); err != nil {
		_ = server.Close()
		return nil, fmt.Errorf("xraybridge: 启动失败: %w", err)
	}
	return &Bridge{server: server, running: true}, nil
}

// Stop 停止桥接实例。重复调用安全（Kotlin 侧停止路径可能被调用多次）。
func (b *Bridge) Stop() error {
	b.mu.Lock()
	defer b.mu.Unlock()
	if !b.running {
		return nil
	}
	b.running = false
	return b.server.Close()
}

// IsRunning 返回桥接是否正在运行（gomobile 友好的状态查询）。
func (b *Bridge) IsRunning() bool {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.running
}

// Version 返回内嵌的 xray-core 版本（core.Version()），用于诊断。
func Version() string {
	return core.Version()
}
