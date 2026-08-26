# iOS setup

For continuous driving location:
1. In Xcode, add Background Modes.
2. Enable Location updates.
3. Add the correct location purpose strings to Info.plist.
4. Start location tracking while the app is active.
5. Configure Core Location background updates for the user-visible driving mode.
6. Minimize battery use and stop when the drive ends.

Typical capability entry:

```xml
<key>UIBackgroundModes</key>
<array>
  <string>location</string>
</array>
```

Do not rely on a browser/PWA or an arbitrary background callback to stay alive forever.
