import 'package:country_code_picker/country_code_picker.dart';
import 'package:flutter/material.dart';

import '../../../../config/theme/app_colors.dart';

class PhoneNumberField extends StatelessWidget {
  const PhoneNumberField({
    super.key,
    required this.controller,
    this.onCountryChanged,
  });

  final TextEditingController controller;
  final Function(CountryCode)? onCountryChanged;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    return Container(
      height: 56,
      decoration: BoxDecoration(
        color: AppColors.white,
        border: Border.all(
          color: AppColors.border,
          width: 1,
        ),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          CountryCodePicker(
            initialSelection: 'PS',
            favorite: const [
              '+970',
              'PS',
            ],
            showFlag: false,
            showCountryOnly: false,
            showOnlyCountryWhenClosed: false,
            showDropDownButton: true,
            showFlagDialog: true,
            alignLeft: false,
            padding: EdgeInsets.zero,
            margin: EdgeInsets.zero,
            onChanged: onCountryChanged,
            textStyle: textTheme.bodyLarge?.copyWith(
              color: AppColors.textPrimary,
              fontWeight: FontWeight.w400,
            ),
            boxDecoration: BoxDecoration(
              color: AppColors.white,
              borderRadius: BorderRadius.circular(12),
              boxShadow: const [],
            ),
          ),

          Container(
            width: 1,
            height: 28,
            color: AppColors.border,
          ),

          const SizedBox(width: 12),

          Expanded(
            child: TextFormField(
              controller: controller,
              keyboardType: TextInputType.phone,
              style: textTheme.bodyLarge?.copyWith(
                color: AppColors.textPrimary,
                fontWeight: FontWeight.w500,
              ),
              decoration: InputDecoration(
                hintText: '5X XXX XXXX',
                hintStyle: textTheme.bodyLarge?.copyWith(
                  color: AppColors.textSecondary,
                  fontWeight: FontWeight.w400,
                ),
                border: InputBorder.none,
                enabledBorder: InputBorder.none,
                focusedBorder: InputBorder.none,
                errorBorder: InputBorder.none,
                focusedErrorBorder: InputBorder.none,
                isCollapsed: true,
                contentPadding: EdgeInsets.zero,
              ),
            ),
          ),

          const SizedBox(width: 16),
        ],
      ),
    );
  }
}