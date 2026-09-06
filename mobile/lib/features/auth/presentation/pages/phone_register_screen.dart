import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:go_router/go_router.dart';
import 'package:mobile/core/constant/app_icons.dart';
import '../../../../config/routes/routes_names.dart';
import '../../../../config/theme/app_colors.dart';
import '../../../../core/widget/app_button.dart';
import '../widgets/phone_number_field.dart';

class PhoneRegisterScreen extends StatefulWidget {
  const PhoneRegisterScreen({super.key});

  @override
  State<PhoneRegisterScreen> createState() => _PhoneRegisterScreenState();
}

class _PhoneRegisterScreenState extends State<PhoneRegisterScreen> {
  final TextEditingController _phoneNumberController = TextEditingController();

  @override
  void dispose() {
    _phoneNumberController.dispose();
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
                "Let's get started!",
                style: textTheme.headlineLarge?.copyWith(
                  color: AppColors.primary,
                ),
              ),

              const SizedBox(height: 16),

              Text(
                "Enter your phone number to create your account",
                style: textTheme.bodyLarge?.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),

              const SizedBox(height: 24),

              Text(
                "Enter Phone Number",
                style: textTheme.labelMedium?.copyWith(
                  color: AppColors.textPrimary,
                ),
              ),

              const SizedBox(height: 12),

              PhoneNumberField(controller: _phoneNumberController),

              const SizedBox(height: 24),

              SizedBox(
                width: double.infinity,
                child: AppElevatedButton(
                  text: 'Send Code',
                  onPressed: null,
                  enabled: false,
                  backgroundColor: AppColors.primary,
                  disabledBackgroundColor: AppColors.disabled,
                  disabledTextColor: AppColors.textSecondary,
                  height: 56,
                  borderRadius: 9999,
                  postIcon: const Icon(Icons.arrow_forward, size: 16),
                ),
              ),

              const Spacer(),

              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    "Already have an account?",
                    style: textTheme.bodySmall?.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  ),
                  TextButton(
                    onPressed: () {
                      context.go(RouteNames.onboardingLoginScreen);
                    },
                    child: const Text("Sign in"),
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
