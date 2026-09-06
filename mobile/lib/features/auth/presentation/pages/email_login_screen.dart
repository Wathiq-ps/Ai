import 'package:flutter/material.dart';
import 'package:flutter_svg/svg.dart';
import 'package:go_router/go_router.dart';

import '../../../../config/routes/routes_names.dart';
import '../../../../config/theme/app_colors.dart';
import '../../../../core/constant/app_icons.dart';
import '../../../../core/widget/app_button.dart';
import '../../../../core/widget/input_field.dart';
import '../widgets/otp_bottom_sheet.dart';

class EmailLoginScreen extends StatefulWidget {
  const EmailLoginScreen({super.key});

  @override
  State<EmailLoginScreen> createState() => _EmailLoginScreenState();
}

class _EmailLoginScreenState extends State<EmailLoginScreen> {
  final TextEditingController _emailController = TextEditingController();

  @override
  void dispose() {
    _emailController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          onPressed: () => Navigator.maybePop(context),
          icon: SvgPicture.asset(AppIcons.back),
        ),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 27),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: 48),

              Text(
                "Welcome back!",
                style: textTheme.headlineLarge?.copyWith(
                  color: AppColors.primary,
                ),
              ),

              const SizedBox(height: 16),

              Text(
                "Enter your email address to sign in your account",
                style: textTheme.bodyLarge?.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),

              const SizedBox(height: 24),

              Text(
                "Enter Email",
                style: textTheme.labelMedium?.copyWith(
                  color: AppColors.textPrimary,
                ),
              ),

              const SizedBox(height: 12),

              InputFieldWidget(
                hint: 'example@mail.com',
                controller: _emailController,
              ),

              const SizedBox(height: 24),

              SizedBox(
                width: double.infinity,
                child: AppElevatedButton(
                  text: 'Continue with Email',
                  onPressed: () {
                    showOtpBottomSheet(context);
                  },
                  backgroundColor: AppColors.white,
                  enableBorder: true,
                  borderColor: AppColors.border,
                  borderWidth: 1,
                  height: 58,
                  borderRadius: 9999,
                  preIcon: SvgPicture.asset(
                    AppIcons.send,
                    width: 24,
                    height: 24,
                  ),
                  textStyle: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    fontSize: 16,
                    fontWeight: FontWeight.w500,
                    color: AppColors.primary,
                  ),
                ),
              ),

              const Spacer(),

              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    "Don't have an account?",
                    style: textTheme.bodySmall?.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  ),
                  TextButton(
                    onPressed: () {
                      context.go(RouteNames.onboardingScreen);
                    },
                    child: const Text("Sign up"),
                  ),
                ],
              ),

              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }
}

void showOtpBottomSheet(BuildContext context) {
  showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => const OtpBottomSheet(),
  );
}
