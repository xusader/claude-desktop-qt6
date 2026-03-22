# Maintainer: xusader
pkgname=claude-desktop-qt6
pkgver=1.0.0
pkgrel=1
pkgdesc="Native Qt6 desktop client for the Anthropic Claude API"
arch=('any')
license=('MIT')
depends=(
    'python'
    'python-pyqt6'
    'python-anthropic'
    'qt6-base'
)
optdepends=(
    'kwin-effects-forceblur: Background blur on KDE Plasma 6 Wayland'
    'kwin-effects-better-blur-dx: Alternative blur effect for KDE Plasma 6'
)
makedepends=()
source=(
    'claude_desktop.py'
    'claude-desktop.sh'
    'claude-desktop.desktop'
    'claude-desktop.svg'
)
sha256sums=('SKIP' 'SKIP' 'SKIP' 'SKIP')

package() {
    cd "${srcdir}"

    install -Dm755 claude_desktop.py \
        "${pkgdir}/usr/lib/${pkgname}/claude_desktop.py"

    install -Dm755 claude-desktop.sh \
        "${pkgdir}/usr/bin/claude-desktop"

    install -Dm644 claude-desktop.desktop \
        "${pkgdir}/usr/share/applications/claude-desktop.desktop"

    install -Dm644 claude-desktop.svg \
        "${pkgdir}/usr/share/icons/hicolor/scalable/apps/claude-desktop.svg"
}
