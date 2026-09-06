import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import 'app_colors.dart';

class AppTheme {
  AppTheme._();

  static ThemeData get light {
    final textTheme = GoogleFonts.alexandriaTextTheme(
      const TextTheme(
        // Headline XL
        // Alexandria / Bold / 700 / 48px
        displayLarge: TextStyle(
          fontSize: 48,
          fontWeight: FontWeight.w700,
          height: 1.2,
        ),

        // Headline LG
        // Alexandria / Bold / 700 / 32px
        headlineLarge: TextStyle(
          fontSize: 32,
          fontWeight: FontWeight.w700,
          height: 1.2,
        ),

        // Body LG
        // Alexandria / Regular / 400 / 18px
        bodyLarge: TextStyle(
          fontSize: 18,
          fontWeight: FontWeight.w400,
          height: 1.5,
        ),

        // Label MD
        // Alexandria / SemiBold / 600 / 14px
        labelMedium: TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w600,
          height: 1.4,
        ),
      ),
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,

      // ─────────────────────────────────────────
      // Colors
      // ─────────────────────────────────────────

      colorScheme: const ColorScheme.light(
        primary: AppColors.primary,
        onPrimary: AppColors.white,

        secondary: AppColors.secondary,
        onSecondary: AppColors.primary,

        tertiary: AppColors.accent,
        onTertiary: AppColors.primary,

        error: AppColors.error,
        onError: AppColors.white,

        surface: AppColors.surface,
        onSurface: AppColors.textPrimary,
      ),

      scaffoldBackgroundColor: AppColors.background,

      // ─────────────────────────────────────────
      // Typography
      // ─────────────────────────────────────────

      textTheme: textTheme,

      // ─────────────────────────────────────────
      // AppBar
      // ─────────────────────────────────────────

      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.white,
        foregroundColor: AppColors.primary,
        elevation: 0,
        centerTitle: false,
      ),

      // ─────────────────────────────────────────
      // Input Fields
      // ─────────────────────────────────────────

      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.white,

        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 16,
        ),

        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(
            color: AppColors.border,
          ),
        ),

        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(
            color: AppColors.border,
          ),
        ),

        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(
            color: AppColors.primary,
            width: 1.5,
          ),
        ),

        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(
            color: AppColors.error,
            width: 1.5,
          ),
        ),

        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(
            color: AppColors.error,
            width: 1.5,
          ),
        ),

        errorStyle: const TextStyle(
          color: AppColors.error,
          fontSize: 12,
          fontWeight: FontWeight.w400,
        ),

        labelStyle: const TextStyle(
          color: AppColors.textSecondary,
        ),

        hintStyle: const TextStyle(
          color: AppColors.textSecondary,
        ),
      ),

      // ─────────────────────────────────────────
      // Elevated Buttons
      // ─────────────────────────────────────────

      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.primary,
          foregroundColor: AppColors.white,
          minimumSize: const Size(
            double.infinity,
            52,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          textStyle: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
          ),
          elevation: 0,
        ),
      ),

      // ─────────────────────────────────────────
      // Text Buttons
      // ─────────────────────────────────────────

      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: AppColors.primary,
          textStyle: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),

      // ─────────────────────────────────────────
      // Divider
      // ─────────────────────────────────────────

      dividerTheme: const DividerThemeData(
        color: AppColors.border,
        thickness: 1,
      ),

      // ─────────────────────────────────────────
      // Checkbox
      // ─────────────────────────────────────────

      checkboxTheme: CheckboxThemeData(
        fillColor: WidgetStateProperty.resolveWith<Color?>(
              (states) {
            if (states.contains(WidgetState.selected)) {
              return AppColors.primary;
            }

            return AppColors.white;
          },
        ),
        side: const BorderSide(
          color: AppColors.border,
        ),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(4),
        ),
      ),

      // ─────────────────────────────────────────
      // SnackBar
      // ─────────────────────────────────────────

      snackBarTheme: SnackBarThemeData(
        backgroundColor: AppColors.primary,
        contentTextStyle: GoogleFonts.alexandria(
          color: AppColors.white,
          fontSize: 14,
          fontWeight: FontWeight.w400,
        ),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
      ),
    );
  }
}