import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:go_router/go_router.dart';
import 'package:mobile/config/routes/routes_names.dart';
import 'package:mobile/features/property/presentation/widgets/header_widget.dart';
import 'package:mobile/features/property/presentation/widgets/submit_button_widget.dart';

import '../../../../config/theme/app_colors.dart';
import '../../../../core/constant/app_icons.dart';
import '../../../../core/constant/images_path.dart';
import '../../../../core/constant/strings.dart';
import '../widgets/property_input_field_widget.dart';

class AddPropertyScreenOne extends StatefulWidget {
  const AddPropertyScreenOne({super.key});

  @override
  State<AddPropertyScreenOne> createState() => _AddPropertyScreenOneState();
}

class _AddPropertyScreenOneState extends State<AddPropertyScreenOne> {
  bool _isForSaleSelected = true;
  int _selectedPropertyTypeIndex = 0;
  final TextEditingController _customTypeController = TextEditingController();

  final List<Map<String, String>> _propertyTypes = const [
    {'title': AppStrings.propertyApartment, 'icon': AppIcons.apartment},
    {'title': AppStrings.propertyVilla, 'icon': AppIcons.villa},
    {'title': AppStrings.propertyLand, 'icon': AppIcons.land},
    {'title': AppStrings.propertyShop, 'icon': AppIcons.shop},
    {'title': AppStrings.propertyHouse, 'icon': AppIcons.house},

    {'title': AppStrings.propertyOther, 'icon': AppIcons.other},
  ];

  @override
  void dispose() {
    _customTypeController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: Stack(
        children: [
          // Background Image
          Positioned.fill(
            child: Image.asset(ImagePath.background, fit: BoxFit.cover),
          ),

          // Main Content
          SafeArea(
            child: Column(
              children: [
                HeaderWidget(
                  title: AppStrings.listYourPropertyTitle,
                  subTitle: AppStrings.listYourPropertyStep1,
                ),
                Expanded(
                  child: SingleChildScrollView(
                    physics: const BouncingScrollPhysics(),
                    padding: const EdgeInsets.symmetric(vertical: 16.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        _buildListingTypeSection(),
                        const SizedBox(height: 24),
                        _buildPropertyTypeGrid(),
                        const SizedBox(height: 24),
                        if (_selectedPropertyTypeIndex == 5) ...[
                          _buildCustomTypeInput(),
                          const SizedBox(height: 33),
                        ],
                        if (_selectedPropertyTypeIndex != 5)
                          const SizedBox(height: 65),
                        SubmitButtonWidget(
                          onPressed: () {
                            context.push(RouteNames.addPropertyScreenTwo);
                          },
                        ),
                        const SizedBox(height: 16),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildListingTypeSection() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 55.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            AppStrings.whatAreYouListing,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              color: AppColors.white,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 12),
          Container(
            height: 52,
            padding: const EdgeInsets.all(4),
            decoration: BoxDecoration(
              color: AppColors.primaryDark,
              borderRadius: BorderRadius.circular(999),
              boxShadow: const [
                BoxShadow(
                  color: AppColors.shadowColor,
                  blurRadius: 4,
                  offset: Offset(0, 4),
                ),
              ],
            ),
            child: Row(
              children: [
                Expanded(
                  child: _buildToggleButton(
                    title: AppStrings.forSale,
                    isSelected: _isForSaleSelected,
                    onTap: () => setState(() => _isForSaleSelected = true),
                  ),
                ),
                Expanded(
                  child: _buildToggleButton(
                    title: AppStrings.forRent,
                    isSelected: !_isForSaleSelected,
                    onTap: () => setState(() => _isForSaleSelected = false),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildToggleButton({
    required String title,
    required bool isSelected,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: isSelected ? AppColors.white : AppColors.transparent,
          borderRadius: BorderRadius.circular(999),
        ),
        child: Text(
          title,
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
            color: isSelected ? AppColors.primaryDark : AppColors.white,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }

  Widget _buildPropertyTypeGrid() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 50),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            AppStrings.propertyType,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              color: AppColors.white,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 12),
          GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              childAspectRatio: 1.8,
              crossAxisSpacing: 14,
              mainAxisSpacing: 24,
            ),
            itemCount: _propertyTypes.length,
            itemBuilder: (context, index) {
              final isSelected = _selectedPropertyTypeIndex == index;
              final item = _propertyTypes[index];
              return _buildPropertyCard(
                title: item['title']!,
                iconPath:   item['icon']!
                   ,
                isSelected: isSelected,
                onTap: () => setState(() => _selectedPropertyTypeIndex = index),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _buildPropertyCard({
    required String title,
    required String iconPath,
    required bool isSelected,
    required VoidCallback onTap,
  }) {
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
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            SvgPicture.asset(iconPath,colorFilter: ColorFilter.mode(
                  isSelected ? AppColors.white : AppColors.white60,
                  BlendMode.srcIn,
                ),),
            const SizedBox(height: 8),
            Text(
              title,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: isSelected ? AppColors.white : AppColors.white70,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCustomTypeInput() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 55.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                AppStrings.specifyPropertyType,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: AppColors.white,
                  fontWeight: FontWeight.w500,
                ),
              ),
              const SizedBox(width: 4),
              Text(
                '*',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: AppColors.errorColor,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          PropertyInputFieldWidget(
            controller: _customTypeController,
            hint: AppStrings.specifyPropertyTypeHint,
          ),
        ],
      ),
    );
  }
}
