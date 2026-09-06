import 'dart:ui';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:mobile/config/routes/routes_names.dart';

class VerifyIdentityScreen extends StatefulWidget {
  const VerifyIdentityScreen({super.key});

  @override
  State<VerifyIdentityScreen> createState() => _VerifyIdentityScreenState();
}

class _VerifyIdentityScreenState extends State<VerifyIdentityScreen> {
  final ImagePicker _picker = ImagePicker();

  XFile? _selectedImage;

  Future<void> _pickImage(ImageSource source) async {
    try {
      final XFile? image = await _picker.pickImage(
        source: source,
        imageQuality: 90,
      );

      if (image != null) {
        setState(() {
          _selectedImage = image;
        });
      }
    } catch (e) {
      debugPrint('Image picker error: $e');
    }
  }

  void _continue() {
    if (_selectedImage == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please upload your ID first')),
      );
      return;
    }

    // انتقل للخطوة الثانية هنا
    // Navigator.push(
    //   context,
    //   MaterialPageRoute(builder: (context) => VerifySelfieIdentityScreen()),
    // );
    context.go(RouteNames.verifySelfieIdentityScreen);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          // =========================
          // Background
          // =========================
          Positioned.fill(
            child: Image.asset(
              'assets/images/onboarding_background.jpg',
              fit: BoxFit.cover,
            ),
          ),

          Positioned.fill(
            child: Container(color: const Color(0xff001B4D).withOpacity(0.72)),
          ),

          Positioned.fill(
            child: BackdropFilter(
              filter: ImageFilter.blur(sigmaX: 2, sigmaY: 2),
              child: Container(color: Colors.transparent),
            ),
          ),

          SafeArea(
            child: Column(
              children: [
                // =========================
                // Header
                // =========================
                Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 20,
                    vertical: 16,
                  ),
                  child: Column(
                    children: [
                      Row(
                        children: [
                          GestureDetector(
                            onTap: () => Navigator.pop(context),
                            child: const Icon(
                              Icons.arrow_back,
                              color: Colors.white,
                              size: 32,
                            ),
                          ),

                          const SizedBox(width: 10),

                          const Expanded(
                            child: Text(
                              'Verify Your Identity',
                              textAlign: TextAlign.center,
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 25,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        ],
                      ),

                      const SizedBox(height: 2),

                      const Text(
                        'Step 1 of 2',
                        style: TextStyle(
                          color: Colors.white70,
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),

                // =========================
                // Main content
                // =========================
                Expanded(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.fromLTRB(20, 0, 20, 2),
                    child: Column(
                      children: [
                        // =========================
                        // Upload Card
                        // =========================
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.fromLTRB(20, 20, 20, 20),
                          decoration: BoxDecoration(
                            color: const Color(0xff8392B8).withOpacity(0.72),
                            borderRadius: BorderRadius.circular(20),
                            border: Border.all(
                              color: Colors.white.withOpacity(0.12),
                            ),
                          ),
                          child: Column(
                            children: [
                              const Text(
                                'Upload your ID',
                                textAlign: TextAlign.center,
                                style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 28,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),

                              const SizedBox(height: 7),

                              const Text(
                                'Take a clear photo of the front of your ID card',
                                textAlign: TextAlign.center,
                                style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 16,
                                  height: 1.45,
                                  fontWeight: FontWeight.w500,
                                ),
                              ),

                              const SizedBox(height: 20),

                              // =========================
                              // Upload Area
                              // =========================
                              GestureDetector(
                                onTap: () {
                                  _pickImage(ImageSource.gallery);
                                },
                                child: CustomPaint(
                                  painter: DashedBorderPainter(
                                    color: Colors.white.withOpacity(0.65),
                                    strokeWidth: 2,
                                    dashWidth: 8,
                                    dashSpace: 6,
                                    radius: 18,
                                  ),
                                  child: Container(
                                    width: double.infinity,
                                    height: 200,
                                    decoration: BoxDecoration(
                                      color: Colors.white.withOpacity(0.08),
                                      borderRadius: BorderRadius.circular(18),
                                    ),
                                    child: _selectedImage == null
                                        ? Column(
                                            mainAxisAlignment:
                                                MainAxisAlignment.center,
                                            children: [
                                              Container(
                                                width: 70,
                                                height: 70,
                                                decoration: const BoxDecoration(
                                                  shape: BoxShape.circle,
                                                  color: Color(0xff001B4D),
                                                ),
                                                child: const Icon(
                                                  Icons.camera_alt_outlined,
                                                  color: Colors.white,
                                                  size: 40,
                                                ),
                                              ),

                                              const SizedBox(height: 10),

                                              const Text(
                                                'Tap to upload',
                                                style: TextStyle(
                                                  color: Colors.white,
                                                  fontSize: 19,
                                                  fontWeight: FontWeight.w700,
                                                ),
                                              ),
                                            ],
                                          )
                                        : ClipRRect(
                                            borderRadius: BorderRadius.circular(
                                              16,
                                            ),
                                            child: Image.file(
                                              File(_selectedImage!.path),
                                              width: double.infinity,
                                              height: double.infinity,
                                              fit: BoxFit.cover,
                                            ),
                                          ),
                                  ),
                                ),
                              ),

                              const SizedBox(height: 20),

                              // =========================
                              // Camera + Gallery buttons
                              // =========================
                              Row(
                                children: [
                                  Expanded(
                                    child: _ActionButton(
                                      icon: Icons.camera_alt_outlined,
                                      text: 'Take Photo',
                                      onTap: () {
                                        _pickImage(ImageSource.camera);
                                      },
                                    ),
                                  ),

                                  const SizedBox(width: 18),

                                  Expanded(
                                    child: _ActionButton(
                                      icon: Icons.image_outlined,
                                      text: 'Gallery',
                                      onTap: () {
                                        _pickImage(ImageSource.gallery);
                                      },
                                    ),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),

                        const SizedBox(height: 15),

                        // =========================
                        // Requirements
                        // =========================
                        const _RequirementItem(
                          text: 'Face and ID both clearly visible',
                        ),

                        const SizedBox(height: 11),

                        const _RequirementItem(
                          text: 'Good lighting, no shadows',
                        ),

                        const SizedBox(height: 11),

                        const _RequirementItem(
                          text: 'Remove sunglasses or hats',
                        ),

                        const SizedBox(height: 11),

                        // =========================
                        // Continue Button
                        // =========================
                        SizedBox(
                          width: double.infinity,
                          height: 66,
                          child: ElevatedButton(
                            onPressed: _continue,
                            style: ElevatedButton.styleFrom(
                              backgroundColor: const Color(0xff001B4D),
                              foregroundColor: Colors.white,
                              elevation: 8,
                              shadowColor: Colors.black.withOpacity(0.35),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(35),
                              ),
                            ),
                            child: const Text(
                              'Continue',
                              style: TextStyle(
                                fontSize: 19,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                        ),

                        const SizedBox(height: 25),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ======================================================
// Action Button
// ======================================================

class _ActionButton extends StatelessWidget {
  final IconData icon;
  final String text;
  final VoidCallback onTap;

  const _ActionButton({
    required this.icon,
    required this.text,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 58,
      child: OutlinedButton.icon(
        onPressed: onTap,
        icon: Icon(icon, color: Colors.white, size: 23),
        label: Text(
          text,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 16,
            fontWeight: FontWeight.w700,
          ),
        ),
        style: OutlinedButton.styleFrom(
          side: BorderSide(color: Colors.white.withOpacity(0.35), width: 1.5),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(30),
          ),
        ),
      ),
    );
  }
}

// ======================================================
// Requirement Item
// ======================================================

class _RequirementItem extends StatelessWidget {
  final String text;

  const _RequirementItem({required this.text});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 42,
          height: 42,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: const Color(0xff173563).withOpacity(0.8),
          ),
          child: const Icon(Icons.check, color: Colors.white, size: 24),
        ),

        const SizedBox(width: 18),

        Expanded(
          child: Text(
            text,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 19,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ],
    );
  }
}

class DashedBorderPainter extends CustomPainter {
  final Color color;
  final double strokeWidth;
  final double dashWidth;
  final double dashSpace;
  final double radius;

  DashedBorderPainter({
    required this.color,
    this.strokeWidth = 2,
    this.dashWidth = 8,
    this.dashSpace = 6,
    this.radius = 18,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = strokeWidth
      ..style = PaintingStyle.stroke;

    final path = Path()
      ..addRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTWH(
            strokeWidth / 2,
            strokeWidth / 2,
            size.width - strokeWidth,
            size.height - strokeWidth,
          ),
          Radius.circular(radius),
        ),
      );

    for (final metric in path.computeMetrics()) {
      double distance = 0;

      while (distance < metric.length) {
        final double nextDistance = distance + dashWidth;

        final Path dash = metric.extractPath(
          distance,
          nextDistance.clamp(0, metric.length),
        );

        canvas.drawPath(dash, paint);

        distance += dashWidth + dashSpace;
      }
    }
  }

  @override
  bool shouldRepaint(covariant DashedBorderPainter oldDelegate) {
    return oldDelegate.color != color ||
        oldDelegate.strokeWidth != strokeWidth ||
        oldDelegate.dashWidth != dashWidth ||
        oldDelegate.dashSpace != dashSpace ||
        oldDelegate.radius != radius;
  }
}
