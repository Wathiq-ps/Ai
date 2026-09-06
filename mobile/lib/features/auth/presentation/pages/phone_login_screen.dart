import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:go_router/go_router.dart';
import '../../../../config/routes/routes_names.dart';
import '../../../../config/theme/app_colors.dart';
import '../../../../core/constant/app_icons.dart';
 import '../../../../core/widget/app_button.dart';
import '../widgets/phone_number_field.dart';


class PhoneLoginScreen extends StatefulWidget {
  const PhoneLoginScreen({super.key});

  @override
  State<PhoneLoginScreen> createState() => _PhoneLoginScreenState();
}

class _PhoneLoginScreenState extends State<PhoneLoginScreen> {
  final TextEditingController _phoneNumberController =
  TextEditingController();

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
          icon: SvgPicture.asset(
            AppIcons.back,
          ),
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
                "Enter your phone number to sign in your account",
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

              PhoneNumberField(
                controller: _phoneNumberController,
              ),

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
                  postIcon: const Icon(
                    Icons.arrow_forward,
                    size: 16,
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
                    context.go(
                         
                        RouteNames.onboardingScreen,
                          
                      );
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