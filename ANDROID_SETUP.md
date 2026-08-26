# Android setup

Add the permissions required by your supported Android versions to
`android/app/src/main/AndroidManifest.xml`, including:

```xml
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION"/>
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>
<uses-permission android:name="android.permission.ACCESS_BACKGROUND_LOCATION"/>
<uses-permission android:name="android.permission.FOREGROUND_SERVICE"/>
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_LOCATION"/>
<uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>
```

For modern Android:
- Start the location foreground service while the app has a visible activity.
- Use foreground service type `location` in the final manifest/plugin config.
- Keep the persistent driving notification visible.
- Request background location only after clearly explaining why.
- Stop high-frequency tracking when the drive ends.
