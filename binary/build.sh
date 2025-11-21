echo "Building binary..."
g++ -std=c++20 -O0 -g main.cpp -o app-bin -ldl -fstack-protector-strong -D_FORTIFY_SOURCE=2 -fPIE -pie -Wl,-z,relro,-z,now
echo "Build complete"
echo "Run with: app-bin"