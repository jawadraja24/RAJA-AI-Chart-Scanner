import 'dart:async';
import 'dart:ui';
import 'package:flutter/widgets.dart';
import 'package:flutter_background_service/flutter_background_service.dart';
import 'package:geolocator/geolocator.dart';

Future<void> configureBackgroundService() async {
  final service = FlutterBackgroundService();
  await service.configure(
    androidConfiguration: AndroidConfiguration(
      onStart: onServiceStart,
      autoStart: false,
      isForegroundMode: true,
      notificationChannelId: 'roadpulse_driving',
      initialNotificationTitle: 'RoadPulse AI',
      initialNotificationContent: 'Driving protection is active',
      foregroundServiceNotificationId: 4201,
    ),
    iosConfiguration: IosConfiguration(
      autoStart: false,
      onForeground: onServiceStart,
      onBackground: onIosBackground,
    ),
  );
}

@pragma('vm:entry-point')
Future<bool> onIosBackground(ServiceInstance service) async {
  WidgetsFlutterBinding.ensureInitialized();
  DartPluginRegistrant.ensureInitialized();
  return true;
}

@pragma('vm:entry-point')
void onServiceStart(ServiceInstance service) async {
  DartPluginRegistrant.ensureInitialized();
  if (service is AndroidServiceInstance) {
    await service.setAsForegroundService();
    await service.setForegroundNotificationInfo(
      title: 'RoadPulse AI',
      content: 'Background driving mode is active',
    );
  }

  Timer.periodic(const Duration(seconds: 20), (timer) async {
    try {
      final position = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.high,
          distanceFilter: 25,
        ),
      );
      service.invoke('location', {
        'lat': position.latitude,
        'lng': position.longitude,
        'speedMps': position.speed,
        'heading': position.heading,
        'timestamp': position.timestamp.toIso8601String(),
      });
      // TODO: send to backend, fetch live traffic/hazards,
      // apply country compliance, then issue allowed alerts.
    } catch (_) {}
  });

  service.on('stop').listen((event) => service.stopSelf());
}
