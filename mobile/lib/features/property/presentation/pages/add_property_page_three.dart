import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:go_router/go_router.dart';
import 'package:mobile/config/routes/routes_names.dart';
import 'package:mobile/features/property/presentation/widgets/header_widget.dart';
import 'package:mobile/features/property/presentation/widgets/property_input_field_widget.dart';

import '../../../../../../../../config/theme/app_colors.dart';
import '../../../../../../../../core/constant/app_icons.dart';
import '../../../../../../../../core/constant/images_path.dart';
import '../../../../../../../../core/constant/strings.dart';
import '../widgets/submit_button_widget.dart';

class AddPropertyScreenThree extends StatefulWidget {
  const AddPropertyScreenThree({super.key});

  @override
  State<AddPropertyScreenThree> createState() => _AddPropertyScreenThreeState();
}

class _AddPropertyScreenThreeState extends State<AddPropertyScreenThree> {
  final TextEditingController _descriptionController = TextEditingController();
  final Set<int> _selectedFeatureIndexes = {};
  final List<Map<String, String>> _features = const [
    {'title': AppStrings.elevator, 'icon': AppIcons.elevator},
    {'title': AppStrings.parking, 'icon': AppIcons.parking},
    {'title': AppStrings.furnished, 'icon': AppIcons.furnished},
    {'title': AppStrings.garden, 'icon': AppIcons.garden},
    {'title': AppStrings.water, 'icon': AppIcons.water},
    {'title': AppStrings.electricity, 'icon': AppIcons.electricity},
    {'title': AppStrings.wifi, 'icon': AppIcons.wifi},
  ];

  @override
  void dispose() {
    _descriptionController.dispose();
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
                  subTitle: AppStrings.listYourPropertyStep3,
                ),
                Expanded(
                  child: SingleChildScrollView(
                    physics: const BouncingScrollPhysics(),
                    padding: const EdgeInsets.symmetric(vertical: 16.0),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 45),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          _buildFeaturesGrid(),
                          SizedBox(height: 37),
                          Text(
                            AppStrings.description,
                            textAlign: TextAlign.center,
                            style: Theme.of(context).textTheme.titleMedium
                                ?.copyWith(
                                  color: AppColors.white,
                                  fontWeight: FontWeight.w600,
                                ),
                          ),
                          const SizedBox(height: 12),
                          PropertyInputFieldWidget(
                            controller: _descriptionController,
                            hint: AppStrings.descriptionHint,
                            maxLines: 4,
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
                SubmitButtonWidget(
                  onPressed: () {
                    context.push(RouteNames.addPropertyScreenFour);
                  },
                ),
                SizedBox(height: 48),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFeaturesGrid() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          AppStrings.features,
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
            mainAxisExtent: 66,
            crossAxisSpacing: 16,
            mainAxisSpacing: 16,
          ),
          itemCount: _features.length - 1,
          itemBuilder: (context, index) {
            final isSelected = _selectedFeatureIndexes.contains(index);
            final item = _features[index];
            return _buildFeatureCard(
              onTap: () => setState(() {
                if (isSelected) {
                  _selectedFeatureIndexes.remove(index);
                } else {
                  _selectedFeatureIndexes.add(index);
                }
              }),
              title: item['title']!,
              iconPath: item['icon']!,
              isSelected: isSelected,
            );
          },
        ),
        SizedBox(height: 16),
        _buildFeatureCard(
          onTap: () => setState(() {
            bool isSelected = _selectedFeatureIndexes.contains(
              _features.length - 1,
            );
            if (isSelected) {
              _selectedFeatureIndexes.remove(_features.length - 1);
            } else {
              _selectedFeatureIndexes.add(_features.length - 1);
            }
          }),
          title: _features.last['title']!,
          iconPath: _features[_features.length - 1]['icon']!,
          isSelected: _selectedFeatureIndexes.contains(_features.length - 1),
        ),
      ],
    );
  }

  Widget _buildFeatureCard({
    required String title,
    required String iconPath,
    required bool isSelected,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        height: 66,
        padding: EdgeInsets.all(12),
        duration: const Duration(milliseconds: 150),
        decoration: BoxDecoration(
          color: isSelected
              ? AppColors.card2SelectedBg
              : AppColors.card2UnselectedBg,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isSelected ? AppColors.white : AppColors.cardBorder,
            width: 1.0,
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.start,
          children: [
            Container(
              width: 40,
              height: 40,
              padding: EdgeInsets.all(11),
              decoration: BoxDecoration(
                color: AppColors.iconBg,
                borderRadius: BorderRadius.circular(45),
              ),
              child: SvgPicture.asset(
                iconPath,
                width: 18,
                height: 18,
                colorFilter: ColorFilter.mode(
                  isSelected ? AppColors.white : AppColors.white70,
                  BlendMode.srcIn,
                ),
              ),
            ),
            const SizedBox(width: 8),
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
}
