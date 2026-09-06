import 'package:flutter/material.dart';
import 'package:mobile/config/theme/app_colors.dart';
import 'package:mobile/core/widget/app_button.dart';

import 'package:pinput/pinput.dart';

class OtpBottomSheet extends StatefulWidget {
  const OtpBottomSheet({super.key});

  @override
  State<OtpBottomSheet> createState() => _OtpBottomSheetState();
}

class _OtpBottomSheetState extends State<OtpBottomSheet> {
  final TextEditingController _otpController = TextEditingController();

  bool _hasError = false;

  @override
  void dispose() {
    _otpController.dispose();
    super.dispose();
  }

  void _verifyOtp() {
    if (_otpController.text != '2222') {
      setState(() {
        _hasError = true;
      });
      return;
    }

    setState(() {
      _hasError = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    final defaultPinTheme = PinTheme(
      width: 64,
      height: 80,
      decoration: BoxDecoration(
        border: Border.all(color: AppColors.border),
        borderRadius: BorderRadius.circular(12),
      ),
    );

    final activePinTheme = PinTheme(
      textStyle: textTheme.headlineLarge?.copyWith(
        fontSize: 30,
        color: AppColors.primary,
      ),
      width: 64,
      height: 80,
      decoration: BoxDecoration(
        border: Border.all(color: AppColors.primary),
        borderRadius: BorderRadius.circular(12),
      ),
    );
    final errorPinTheme = PinTheme(
      textStyle: textTheme.headlineLarge?.copyWith(
        fontSize: 30,
        color: AppColors.primary,
      ),
      width: 64,
      height: 80,
      decoration: BoxDecoration(
        border: Border.all(color: AppColors.error),
        borderRadius: BorderRadius.circular(12),
      ),
    );
    return Padding(
      padding: EdgeInsets.only(
        bottom: MediaQuery.of(context).viewInsets.bottom,
      ),
      child: Container(
        padding: const EdgeInsets.all(24),
        decoration: const BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.vertical(top: Radius.circular(35)),
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Enter Code',
                style: textTheme.headlineLarge?.copyWith(
                  fontSize: 30,
                  color: AppColors.primary,
                ),
              ),
              SizedBox(height: 8),
              Text(
                'We sent a 4-digit verification code to your email. Please enter it below.',
                style: textTheme.bodyLarge?.copyWith(
                  fontSize: 16,
                  color: AppColors.primary,
                ),
              ),
              SizedBox(height: 48),

              Pinput(
                length: 4,
                controller: _otpController,
                defaultPinTheme: defaultPinTheme,
                focusedPinTheme: activePinTheme,
                submittedPinTheme: activePinTheme,
                errorPinTheme: errorPinTheme,
                keyboardType: TextInputType.number,
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                showCursor: true,

                forceErrorState: _hasError,
                onChanged: (_) {
                  if (_hasError) {
                    setState(() {
                      _hasError = false;
                    });
                  }
                },
              ),
              if (_hasError) ...[
                const SizedBox(height: 12),
                Text(
                  "The code you entered doesn't match. Please try again",
                  style: textTheme.bodyLarge?.copyWith(
                    fontSize: 12,
                    color: AppColors.error,
                  ),
                ),
              ],
              SizedBox(height: 48),
              AppElevatedButton(
                text: 'Verify and Proceed',
                onPressed: _verifyOtp,
              ),
              SizedBox(height: 24),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    "Didn't receive the code? ",
                    style: textTheme.bodyLarge?.copyWith(
                      fontSize: 14,
                      color: AppColors.primary,
                    ),
                  ),
                  TextButton(
                    onPressed: () {},
                    style: TextButton.styleFrom(
                      foregroundColor: AppColors.primary,
                      textStyle: textTheme.bodyLarge?.copyWith(
                        fontSize: 14,
                        color: AppColors.primary,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    child: Text("Resend"),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
