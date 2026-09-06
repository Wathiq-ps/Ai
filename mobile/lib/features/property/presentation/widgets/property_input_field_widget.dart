import 'package:flutter/material.dart';

import '../../../../config/theme/app_colors.dart';

class PropertyInputFieldWidget extends StatelessWidget {
  const PropertyInputFieldWidget({
    super.key,
    required this.controller,
    required this.hint,
    this.validator,
    this.obscureText = false,
    this.suffixIcon,
    this.suffix,
    this.suffixText,
    this.prefixIcon,
    this.maxLines,
  });

  final TextEditingController controller;
  final String hint;
  final String? suffixText;

  final String? Function(String? value)? validator;
  final bool obscureText;

  final Widget? suffixIcon;
  final Widget? suffix;

  final Widget? prefixIcon;
  final int? maxLines;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    return TextFormField(
      controller: controller,
      validator: validator,
      obscureText: obscureText,
      maxLines: maxLines,
      style: textTheme.bodyLarge?.copyWith(color: AppColors.white),

      decoration: InputDecoration(
        hintText: hint,

        // The rest of the field styling comes from AppTheme.
        filled: true,
        fillColor: AppColors.cardSelectedBg,

        contentPadding: const EdgeInsets.symmetric(
          horizontal: 18,
          vertical: 18,
        ),

        floatingLabelBehavior: FloatingLabelBehavior.never,

        prefixIcon: prefixIcon,
        suffix: suffix,
        suffixText: suffixText,
        suffixIcon: 
        
       
        suffixIcon,
       
        // 2. Adjust alignment constraints if the widget looks too large
       // suffixIconConstraints: const BoxConstraints(minWidth: 0, minHeight: 0),
        prefixIconColor: AppColors.textSecondary,
        suffixIconColor: AppColors.textSecondary,

        hintStyle: textTheme.bodyLarge?.copyWith(color: AppColors.white40),

        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.cardBorder, width: 1),
        ),

        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.white, width: 1),
        ),

        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.error, width: 1),
        ),

        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.error, width: 1),
        ),

        errorStyle: textTheme.bodySmall?.copyWith(color: AppColors.error),
      ),
    );
  }
}
