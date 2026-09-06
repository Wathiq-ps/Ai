import 'package:flutter/material.dart';

import '../../../../config/theme/app_colors.dart';

class CardWidget extends StatelessWidget {
  final Widget widget;
  final bool isSelected;
  final VoidCallback onTap;

  const CardWidget({
    super.key,
    required this.widget,

    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        decoration: BoxDecoration(
          color: isSelected
              ? AppColors.cardSelectedBg
              : AppColors.cardUnselectedBg,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isSelected ? AppColors.white : AppColors.cardBorder,
            width: isSelected ? 2.0 : 1.0,
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8,vertical: 8),
          child: widget,
        ),
      ),
    );
  }
}
