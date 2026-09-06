import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:mobile/features/property/presentation/widgets/header_widget.dart';

import '../../../../../../../../config/theme/app_colors.dart';
import '../../../../../../../../core/constant/app_icons.dart';
import '../../../../../../../../core/constant/images_path.dart';
import '../../../../../../../../core/constant/strings.dart';
import '../../../../core/services/image_picker_service.dart';
import '../../../../core/widget/dashed_border.dart';
import '../widgets/submit_button_widget.dart';

class AddPropertyScreenFour extends StatefulWidget {
  const AddPropertyScreenFour({super.key});

  @override
  State<AddPropertyScreenFour> createState() => _AddPropertyScreenFourState();
}

class _AddPropertyScreenFourState extends State<AddPropertyScreenFour> {
  final List<String> _photos = [];
  static const int _maxPhotos = 10;
  final ImagePickerService _imagePickerService = ImagePickerService();

  Future<void> _pickImages() async {
    final remainingPhotos = _maxPhotos - _photos.length;

    if (remainingPhotos <= 0) return;

    try {
      final images = await _imagePickerService.pickImages(
        limit: remainingPhotos,
      );

      if (!mounted || images.isEmpty) return;

      setState(() {
        _photos.addAll(images);
      });
    } catch (e) {
      debugPrint('Image picker error: $e');
    }
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
                  subTitle: AppStrings.listYourPropertyStep4,
                ),
                Expanded(
                  child: SingleChildScrollView(
                    physics: const BouncingScrollPhysics(),
                    padding: const EdgeInsets.symmetric(vertical: 16.0),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 24),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          SizedBox(height: 37),
                          Text(
                            AppStrings.propertyPhotos,

                            style: Theme.of(context).textTheme.titleMedium
                                ?.copyWith(color: AppColors.white),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            AppStrings.addPhotosDescription,

                            style: Theme.of(context).textTheme.titleMedium
                                ?.copyWith(color: AppColors.white70),
                          ),
                          const SizedBox(height: 26),
                          // _buildAddPhotoWidget(context),
                          _buildPhotosGrid(),
                        ],
                      ),
                    ),
                  ),
                ),
                SubmitButtonWidget(onPressed: () {}),
                SizedBox(height: 48),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPhotosGrid() {
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 3,
        mainAxisExtent: 95,
        crossAxisSpacing: 14,
        mainAxisSpacing: 14,
      ),
      itemCount: _photos.length + 1,
      itemBuilder: (context, index) {
        if (index == 0) {
          return _buildAddPhotoWidget(context);
        }

        final photo = _photos[index - 1];

        return photoItem(photo);
      },
    );
  }

  Widget photoItem(String photo) {
    return Stack(
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(12),
          child: Image.file(
            File(photo),
            width: double.infinity,
            height: double.infinity,
            fit: BoxFit.cover,
          ),
        ),

        Positioned(
          top: 6,
          right: 6,
          child: GestureDetector(
            onTap: () => _deletePhoto(photo),
            child: Container(
              width: 24,
              height: 24,
              decoration: const BoxDecoration(
                shape: BoxShape.circle,
                color: AppColors.iconBg,
              ),
              child: Center(
                child: SizedBox(
                  width: 10,
                  height: 10,
                  child: SvgPicture.asset(AppIcons.remove, fit: BoxFit.contain),
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildAddPhotoWidget(BuildContext context) {
    return GestureDetector(
      onTap: () {
        _pickImages();
      },
      child: CustomPaint(
        painter: DashedBorderPainter(
          color: AppColors.photoBorder,
          strokeWidth: 2,
          dashWidth: 6,
          dashSpace: 4,
          radius: 12,
        ),
        child: Container(
          width: 95,
          height: 95,
          decoration: BoxDecoration(
            color: AppColors.addPhotoBg,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                SvgPicture.asset(
                  AppIcons.addPhoto,
                  colorFilter: ColorFilter.mode(
                    _photos.length == 10 ? AppColors.white40 : AppColors.white,
                    BlendMode.srcIn,
                  ),
                ),
                SizedBox(height: 4),
                Text(
                  AppStrings.add,
                  style: Theme.of(context).textTheme.bodySmall!.copyWith(
                    color: _photos.length == 10
                        ? AppColors.white40
                        : AppColors.white,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _deletePhoto(String photo) {
    setState(() {
      _photos.remove(photo);
    });
  }
}
