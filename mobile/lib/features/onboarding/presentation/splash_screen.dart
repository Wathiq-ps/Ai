import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:mobile/config/routes/routes_names.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with TickerProviderStateMixin {
  late AnimationController _logoController;
  late AnimationController _fadeController;
  late AnimationController _backgroundController;
  late AnimationController _groupLogoController;

  late Animation<double> _logoScale;
  late Animation<double> _fadeAnimation;
  late Animation<double> _backgroundAnimation;
  late Animation<double> _groupLogoScale;
  late Animation<double> _groupLogoFade;

  @override
  void initState() {
    super.initState();

    // تكبير الشعار الأول
    _logoController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 5),
    );

    _logoScale = Tween<double>(
      begin: 10 / 200,
      end: 1,
    ).animate(CurvedAnimation(parent: _logoController, curve: Curves.linear));

    // اختفاء الشعار الأول
    _fadeController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 500),
    );

    _fadeAnimation = Tween<double>(begin: 1, end: 0).animate(_fadeController);

    // تغيير الخلفية
    _backgroundController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 700),
    );

    _backgroundAnimation = Tween<double>(begin: 0, end: 1).animate(
      CurvedAnimation(parent: _backgroundController, curve: Curves.easeInOut),
    );

    // ظهور شعار المجموعة
    _groupLogoController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 700),
    );

    _groupLogoScale = Tween<double>(begin: 0.5, end: 1).animate(
      CurvedAnimation(parent: _groupLogoController, curve: Curves.easeOutBack),
    );

    _groupLogoFade = Tween<double>(
      begin: 0,
      end: 1,
    ).animate(_groupLogoController);

    startAnimation();
  }

  Future<void> startAnimation() async {
    // تكبير الشعار الأول
    await _logoController.forward();

    // إخفاء الشعار
    await _fadeController.forward();

    // تغيير الخلفية
    await _backgroundController.forward();

    // إظهار شعار المجموعة
    await _groupLogoController.forward();

    // انتظار ثانية
    await Future.delayed(const Duration(seconds: 1));

    if (!mounted) return;

    // Navigator.pushReplacement(
    //   context,
    //   MaterialPageRoute(builder: (_) => const VerifyIdentityScreen()),
    // );
    context.go(RouteNames.proofOfOwnershipPage);
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: Listenable.merge([
        _backgroundController,
        _logoController,
        _fadeController,
        _groupLogoController,
      ]),

      builder: (context, child) {
        return Scaffold(
          body: Container(
            width: double.infinity,
            height: double.infinity,

            color: Color.lerp(
              Colors.white,
              const Color(0xFF00113A),
              _backgroundAnimation.value,
            ),

            child: Center(
              child: Stack(
                alignment: Alignment.center,

                children: [
                  // الشعار الأول
                  Opacity(
                    opacity: _fadeAnimation.value,

                    child: Transform.scale(
                      scale: _logoScale.value,

                      child: Image.asset(
                        'assets/images/logo.png',
                        width: 200,
                        height: 200,
                        fit: BoxFit.contain,
                      ),
                    ),
                  ),

                  // شعار المجموعة
                  Opacity(
                    opacity: _groupLogoFade.value,

                    child: Transform.scale(
                      scale: _groupLogoScale.value,

                      child: Image.asset('assets/images/group1.png'),
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  @override
  void dispose() {
    _logoController.dispose();
    _fadeController.dispose();
    _backgroundController.dispose();
    _groupLogoController.dispose();

    super.dispose();
  }
}
