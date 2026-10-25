#!/bin/sh
# Build "Battery Notifier.app" into target/release/, for Apple Silicon and Intel Macs, ad-hoc signed.
# Needs both targets: rustup target add aarch64-apple-darwin x86_64-apple-darwin
set -eu
cd "$(dirname "$0")/.."

version=$(sed -n 's/^version = "\(.*\)"$/\1/p' Cargo.toml | head -n 1)
for target in aarch64-apple-darwin x86_64-apple-darwin; do
    cargo build --release --locked --target "$target"
done

app="target/release/Battery Notifier.app"
rm -rf "$app"
mkdir -p "$app/Contents/MacOS"
lipo -create -output "$app/Contents/MacOS/battery-notifier" \
    target/aarch64-apple-darwin/release/battery-notifier \
    target/x86_64-apple-darwin/release/battery-notifier
sed "s/@VERSION@/$version/" macos/Info.plist > "$app/Contents/Info.plist"
codesign --force --sign - "$app"
