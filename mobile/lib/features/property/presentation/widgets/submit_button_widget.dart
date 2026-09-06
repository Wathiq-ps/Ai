import 'package:flutter/material.dart';

import '../../../../config/theme/app_colors.dart';
import '../../../../core/constant/strings.dart';
import '../../../../core/widget/app_button.dart';

class SubmitButtonWidget extends StatelessWidget {
  final VoidCallback onPressed;
  const SubmitButtonWidget({super.key, required this.onPressed});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 25),
      child: AppElevatedButton(
        text: AppStrings.continueText,
        height: 56,
        width: double.infinity,
        borderRadius: 999,
        backgroundColor: AppColors.primaryDark,
        onPressed: onPressed,
      ),
    );
  }
}
