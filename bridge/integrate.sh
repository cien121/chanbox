#!/bin/bash
# ChanBox Xray 桥接集成脚本
# 在 workflow 的 "Customize branding and theme" 之后、"Build libcore" 之前运行
# working-directory: nekobox
set -e

# xray-core v26.3.27 的 commit hash。
# 注意：不能直接 require v26.3.27 标签，因为 xray-core 的 go.mod 模块路径
# 是 github.com/xtls/xray-core（无 /v26 后缀），Go modules 拒绝 v2+ 大版本
# 无后缀的 require。用 commit hash 让 go get 自动生成 pseudo-version。
XRAY_COMMIT="d2758a023cd7f4174a5a5fa4ff66e487d4342ba0"

echo ">>> [xraybridge] 复制桥接代码"
mkdir -p libcore/xraybridge
cp -f ../chanbox-assets/bridge/bridge/xraybridge/bridge.go libcore/xraybridge/bridge.go

echo ">>> [xraybridge] 拉取 sing-box/libneko 源码（供 go.mod replace 解析）"
# libcore/go.mod 有 replace github.com/matsuridayo/libneko => ../../libneko
# 和 replace github.com/sagernet/sing-box => ../../sing-box，
# 必须先拉取，否则 go get 解析 replace 会失败。
# 注意：不能直接跑 buildScript/lib/core/get_source.sh，因为它会 source env.sh
# 进而要求 NDK 就绪，而此时 NDK 还没装好。这里只做 git clone，不碰 NDK。
source "buildScript/lib/core/get_source_env.sh"
if [ ! -d "../sing-box" ]; then
  git clone --no-checkout https://github.com/MatsuriDayo/sing-box.git ../sing-box
fi
pushd ../sing-box > /dev/null
git checkout "$COMMIT_SING_BOX"
popd > /dev/null
if [ ! -d "../libneko" ]; then
  git clone --no-checkout https://github.com/MatsuriDayo/libneko.git ../libneko
fi
pushd ../libneko > /dev/null
git checkout "$COMMIT_LIBNEKO"
popd > /dev/null

echo ">>> [xraybridge] 添加 xray-core 依赖 (commit: $XRAY_COMMIT)"
cd libcore
if ! grep -q "github.com/xtls/xray-core" go.mod; then
  go get github.com/xtls/xray-core@$XRAY_COMMIT
fi

echo ">>> [xraybridge] 更新 go.sum"
go mod tidy

echo ">>> [xraybridge] 修改 build.sh 以包含 xraybridge 包"
# bind 命令末尾是 " ."（待绑定的包），改成 " . ./xraybridge"
if ! grep -q '\./xraybridge' build.sh; then
  sed -i 's# \. || exit 1# . ./xraybridge || exit 1#' build.sh
fi

echo ">>> [xraybridge] 验证 build.sh"
grep -o "gomobile-matsuri bind.*\./xraybridge" build.sh || {
  echo "ERROR: build.sh 未成功加入 ./xraybridge"
  exit 1
}

echo ">>> [xraybridge] 集成完成"
cd ..

