import 'package:flutter/material.dart';
import 'package:flutter_background_service/flutter_background_service.dart';
import 'package:geolocator/geolocator.dart';
import 'background_service.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await configureBackgroundService();
  runApp(const RoadPulseApp());
}

class RoadPulseApp extends StatelessWidget {
  const RoadPulseApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'RoadPulse AI',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF17B36B)),
        useMaterial3: true,
      ),
      home: const DriveHome(),
    );
  }
}

class DriveHome extends StatefulWidget {
  const DriveHome({super.key});
  @override
  State<DriveHome> createState() => _DriveHomeState();
}

class _DriveHomeState extends State<DriveHome> {
  bool tracking = false;
  String status = 'Ready';

  Future<bool> ensurePermission() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      setState(() => status = 'Turn on Location Services first.');
      return false;
    }
    var p = await Geolocator.checkPermission();
    if (p == LocationPermission.denied) p = await Geolocator.requestPermission();
    if (p == LocationPermission.denied || p == LocationPermission.deniedForever) {
      setState(() => status = 'Location permission is required.');
      return false;
    }
    return true;
  }

  Future<void> startDrive() async {
    if (!await ensurePermission()) return;
    await FlutterBackgroundService().startService();
    setState(() { tracking = true; status = 'Background driving mode active'; });
  }

  Future<void> stopDrive() async {
    FlutterBackgroundService().invoke('stop');
    setState(() { tracking = false; status = 'Driving mode stopped'; });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('RoadPulse AI')),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Container(
            height: 310,
            decoration: BoxDecoration(
              color: const Color(0xFFEAF3EF),
              borderRadius: BorderRadius.circular(24),
            ),
            child: const Center(child: Text('Map / traffic / incident layer goes here')),
          ),
          const SizedBox(height: 18),
          Text(status, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: tracking ? stopDrive : startDrive,
            icon: Icon(tracking ? Icons.stop_circle : Icons.directions_car),
            label: Text(tracking ? 'Stop Driving Mode' : 'Start Driving Mode'),
          ),
          const SizedBox(height: 10),
          const Text('Alert behavior must follow country compliance rules and user permissions.'),
        ]),
      ),
    );
  }
}
