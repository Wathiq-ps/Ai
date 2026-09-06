import 'package:flutter/material.dart';

import '../../config/theme/app_colors.dart';
import '../extensions/media_query_extensions.dart';

class InputFieldWidget extends StatelessWidget {
  const InputFieldWidget({
    super.key,
    required this.controller,
    required this.hint,
    this.errorText,
    this.onChanged,
    this.obscureText = false,
    this.suffixIcon,
    this.prefixIcon,
  });

  final TextEditingController controller;
  final String hint;
  final String? errorText;
  final ValueChanged<String>? onChanged;
  final bool obscureText;
  final Widget? suffixIcon;
  final Widget? prefixIcon;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    // Figma reference dimensions.
    final _figmaWidth = 393;
    final _figmaHeight = 852;

    final _currentScreenWidth = context.screenWidth;
    final _currentScreenHeight = context.screenHeight;

    final _widthScale = _currentScreenWidth / _figmaWidth;
    final _heightScale = _currentScreenHeight / _figmaHeight;

    const double figmaBorderRadius = 12;
    const double figmaHorizontalPadding = 16;
    const double figmaVerticalPadding = 16;
    const double figmaFontSize = 16;
    const double figmaLineHeight = 24;

    return TextFormField(
      controller: controller,
      onChanged: onChanged,
      obscureText: obscureText,
      style: textTheme.bodyLarge?.copyWith(
        color: AppColors.textPrimary,
        fontSize: figmaFontSize * _widthScale,
        height: figmaLineHeight / figmaFontSize,
      ),
      decoration: InputDecoration(
        hintText: hint,

        // Cubit validation error.
        errorText: errorText,

        filled: true,
        fillColor: AppColors.white,

        contentPadding: EdgeInsets.symmetric(
          horizontal: figmaHorizontalPadding * _widthScale,
          vertical: figmaVerticalPadding * _heightScale,
        ),

        floatingLabelBehavior: FloatingLabelBehavior.never,

        prefixIcon: prefixIcon,
        suffixIcon: suffixIcon,

        prefixIconColor: AppColors.textSecondary,
        suffixIconColor: AppColors.textSecondary,

        hintStyle: textTheme.bodyLarge?.copyWith(
          color: AppColors.textSecondary,
          fontSize: figmaFontSize * _widthScale,
          height: figmaLineHeight / figmaFontSize,
        ),

        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(
            figmaBorderRadius * _widthScale,
          ),
          borderSide: const BorderSide(
            color: AppColors.border,
            width: 1,
          ),
        ),

        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(
            figmaBorderRadius * _widthScale,
          ),
          borderSide: const BorderSide(
            color: AppColors.primary,
            width: 1.5,
          ),
        ),

        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(
            figmaBorderRadius * _widthScale,
          ),
          borderSide: const BorderSide(
            color: AppColors.error,
            width: 1.5,
          ),
        ),

        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(
            figmaBorderRadius * _widthScale,
          ),
          borderSide: const BorderSide(
            color: AppColors.error,
            width: 1.5,
          ),
        ),

        errorStyle: textTheme.bodySmall?.copyWith(
          color: AppColors.error,
          fontSize: 12 * _widthScale,
        ),
      ),
    );
  }
}