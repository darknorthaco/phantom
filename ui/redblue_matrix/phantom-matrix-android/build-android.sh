#!/bin/bash

# Phantom Matrix AI - Android Build Script
# Dark North Co. - Your AI. Your Hardware. Your Rules.

echo "🔋 Building Phantom Matrix AI for Android..."
echo "================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    echo -e "${RED}❌ Error: package.json not found. Please run this script from the project root.${NC}"
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Error: Node.js is not installed. Please install Node.js first.${NC}"
    exit 1
fi

# Check if React Native CLI is installed
if ! command -v npx &> /dev/null; then
    echo -e "${RED}❌ Error: npx is not available. Please install npm/npx first.${NC}"
    exit 1
fi

echo -e "${CYAN}📦 Installing dependencies...${NC}"
npm install

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to install dependencies${NC}"
    exit 1
fi

echo -e "${CYAN}🔧 Setting up Android environment...${NC}"

# Check if Android SDK is available
if [ -z "$ANDROID_HOME" ]; then
    echo -e "${YELLOW}⚠️  Warning: ANDROID_HOME not set. Please set up Android SDK.${NC}"
    echo -e "${YELLOW}   You can download Android Studio from: https://developer.android.com/studio${NC}"
fi

# Create android directory structure if it doesn't exist
if [ ! -d "android" ]; then
    echo -e "${CYAN}🏗️  Initializing Android project...${NC}"
    npx react-native init PhantomMatrixTemp --template react-native-template-typescript
    cp -r PhantomMatrixTemp/android ./
    rm -rf PhantomMatrixTemp
fi

echo -e "${CYAN}🎨 Configuring Matrix theme...${NC}"

# Ensure all Android resources are in place
mkdir -p android/app/src/main/res/mipmap-hdpi
mkdir -p android/app/src/main/res/mipmap-mdpi
mkdir -p android/app/src/main/res/mipmap-xhdpi
mkdir -p android/app/src/main/res/mipmap-xxhdpi
mkdir -p android/app/src/main/res/mipmap-xxxhdpi

echo -e "${GREEN}✅ Android project structure ready${NC}"

# Build options
echo -e "${CYAN}🚀 Choose build type:${NC}"
echo "1) Debug APK (for testing)"
echo "2) Release APK (for distribution)"
echo "3) Android App Bundle (for Play Store)"
echo "4) Install on connected device"

read -p "Enter your choice (1-4): " choice

case $choice in
    1)
        echo -e "${CYAN}🔨 Building debug APK...${NC}"
        cd android
        ./gradlew assembleDebug
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✅ Debug APK built successfully!${NC}"
            echo -e "${GREEN}📱 APK location: android/app/build/outputs/apk/debug/app-debug.apk${NC}"
        else
            echo -e "${RED}❌ Debug build failed${NC}"
            exit 1
        fi
        ;;
    2)
        echo -e "${CYAN}🔨 Building release APK...${NC}"
        cd android
        ./gradlew assembleRelease
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✅ Release APK built successfully!${NC}"
            echo -e "${GREEN}📱 APK location: android/app/build/outputs/apk/release/app-release.apk${NC}"
        else
            echo -e "${RED}❌ Release build failed${NC}"
            exit 1
        fi
        ;;
    3)
        echo -e "${CYAN}🔨 Building Android App Bundle...${NC}"
        cd android
        ./gradlew bundleRelease
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✅ App Bundle built successfully!${NC}"
            echo -e "${GREEN}📱 AAB location: android/app/build/outputs/bundle/release/app-release.aab${NC}"
        else
            echo -e "${RED}❌ Bundle build failed${NC}"
            exit 1
        fi
        ;;
    4)
        echo -e "${CYAN}📱 Installing on connected device...${NC}"
        npx react-native run-android
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✅ App installed and launched successfully!${NC}"
        else
            echo -e "${RED}❌ Installation failed${NC}"
            exit 1
        fi
        ;;
    *)
        echo -e "${RED}❌ Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}🎉 Phantom Matrix AI build complete!${NC}"
echo -e "${CYAN}================================================${NC}"
echo -e "${CYAN}🔋 Dark North Co. - Your AI. Your Hardware. Your Rules.${NC}"
echo -e "${CYAN}================================================${NC}"