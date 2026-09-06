import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

class ProofOfOwnershipPage extends StatefulWidget {
  const ProofOfOwnershipPage({super.key});

  @override
  State<ProofOfOwnershipPage> createState() => _ProofOfOwnershipPageState();
}

class _ProofOfOwnershipPageState extends State<ProofOfOwnershipPage> {
  final ImagePicker _imagePicker = ImagePicker();

  final List<File> _files = [];

  // ------------------------------------------------------------
  // Take Photo
  // ------------------------------------------------------------
  Future<void> _takePhoto() async {
    final XFile? image = await _imagePicker.pickImage(
      source: ImageSource.camera,
      imageQuality: 85,
    );

    if (image == null) return;

    setState(() {
      _files.add(File(image.path));
    });
  }

  // ------------------------------------------------------------
  // Gallery
  // ------------------------------------------------------------
  Future<void> _pickFromGallery() async {
    final List<XFile> images = await _imagePicker.pickMultiImage(
      imageQuality: 85,
    );

    if (images.isEmpty) return;

    setState(() {
      _files.addAll(images.map((image) => File(image.path)));
    });
  }

  // ------------------------------------------------------------
  // File
  // ------------------------------------------------------------
  Future<void> _pickFile() async {
    final files = await FilePicker.pickFiles(
      allowMultiple: true,
      type: FileType.custom,
      allowedExtensions: ['pdf', 'jpg', 'jpeg', 'png'],
    );

    if (files.isEmpty) return;

    final selectedFiles = files
        .where((file) => file.path != null)
        .map((file) => File(file.path!))
        .toList();

    setState(() {
      _files.addAll(selectedFiles);
    });
  }

  // ------------------------------------------------------------
  // Remove file
  // ------------------------------------------------------------
  void _removeFile(int index) {
    setState(() {
      _files.removeAt(index);
    });
  }

  // ------------------------------------------------------------
  // Continue
  // ------------------------------------------------------------
  void _continue() {
    if (_files.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please upload at least one document')),
      );
      return;
    }

    // هنا ترسل الملفات إلى Laravel API
    //
    // مثال:
    // await uploadDocuments(_files);

    debugPrint('Selected files: ${_files.length}');
  }

  // ------------------------------------------------------------
  // File preview
  // ------------------------------------------------------------
  Widget _buildFilePreview(File file, int index) {
    final extension = file.path.split('.').last.toLowerCase();

    final isImage = ['jpg', 'jpeg', 'png', 'webp'].contains(extension);

    return Stack(
      clipBehavior: Clip.none,
      children: [
        Container(
          width: 100,
          height: 100,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: Colors.white.withOpacity(0.35), width: 1),
          ),
          clipBehavior: Clip.antiAlias,
          child: isImage
              ? Image.file(file, fit: BoxFit.cover)
              : Container(
                  color: Colors.white.withOpacity(0.12),
                  child: const Center(
                    child: Icon(
                      Icons.picture_as_pdf,
                      color: Colors.white,
                      size: 42,
                    ),
                  ),
                ),
        ),

        // Remove button
        Positioned(
          top: -7,
          right: -7,
          child: GestureDetector(
            onTap: () => _removeFile(index),
            child: Container(
              width: 28,
              height: 28,
              decoration: const BoxDecoration(
                color: Color(0xFF6B7280),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.close, color: Colors.white, size: 18),
            ),
          ),
        ),
      ],
    );
  }

  // ------------------------------------------------------------
  // Add file button
  // ------------------------------------------------------------
  Widget _buildAddButton() {
    return GestureDetector(
      onTap: _showUploadOptions,
      child: Container(
        width: 100,
        height: 100,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: Colors.white.withOpacity(0.25), width: 1),
        ),
        child: const Center(
          child: Icon(Icons.add, color: Colors.white, size: 40),
        ),
      ),
    );
  }

  // ------------------------------------------------------------
  // Upload options
  // ------------------------------------------------------------
  void _showUploadOptions() {
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF071C4C),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (context) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                ListTile(
                  leading: const Icon(Icons.camera_alt, color: Colors.white),
                  title: const Text(
                    'Take Photo',
                    style: TextStyle(color: Colors.white),
                  ),
                  onTap: () {
                    Navigator.pop(context);
                    _takePhoto();
                  },
                ),
                ListTile(
                  leading: const Icon(Icons.photo_library, color: Colors.white),
                  title: const Text(
                    'Gallery',
                    style: TextStyle(color: Colors.white),
                  ),
                  onTap: () {
                    Navigator.pop(context);
                    _pickFromGallery();
                  },
                ),
                ListTile(
                  leading: const Icon(
                    Icons.insert_drive_file,
                    color: Colors.white,
                  ),
                  title: const Text(
                    'File',
                    style: TextStyle(color: Colors.white),
                  ),
                  onTap: () {
                    Navigator.pop(context);
                    _pickFile();
                  },
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  // ------------------------------------------------------------
  // Upload button
  // ------------------------------------------------------------
  Widget _uploadButton({
    required IconData icon,
    required String text,
    required VoidCallback onTap,
  }) {
    return Expanded(
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          height: 58,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(30),
            border: Border.all(color: Colors.white, width: 1.5),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, color: Colors.white, size: 25),
              const SizedBox(width: 10),
              Text(
                text,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 17,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ------------------------------------------------------------
  // Build
  // ------------------------------------------------------------
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          // Background image
          Positioned.fill(
            child: Image.asset(
              'assets/images/background.png',
              fit: BoxFit.cover,
            ),
          ),

          // Blue overlay
          Positioned.fill(
            child: Container(color: const Color(0xFF001B55).withOpacity(0.78)),
          ),

          SafeArea(
            child: Column(
              children: [
                // ------------------------------------------------
                // Header
                // ------------------------------------------------
                Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 20,
                    vertical: 18,
                  ),
                  child: Row(
                    children: [
                      GestureDetector(
                        onTap: () {
                          Navigator.pop(context);
                        },
                        child: const Icon(
                          Icons.arrow_back,
                          color: Colors.white,
                          size: 32,
                        ),
                      ),

                      const SizedBox(width: 20),

                      const Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Proof of Ownership',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 30,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            SizedBox(height: 5),
                            Text(
                              'Step 5 of 6',
                              style: TextStyle(
                                color: Color(0xFFD5DDF0),
                                fontSize: 18,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),

                // ------------------------------------------------
                // Main content
                // ------------------------------------------------
                Expanded(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.fromLTRB(20, 80, 20, 20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Upload documents',
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 22,
                            fontWeight: FontWeight.bold,
                          ),
                        ),

                        const SizedBox(height: 28),

                        // Upload area
                        GestureDetector(
                          onTap: _showUploadOptions,
                          child: Container(
                            width: double.infinity,
                            height: 430,
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(30),
                              border: Border.all(
                                color: Colors.white,
                                width: 2,
                                style: BorderStyle.solid,
                              ),
                              color: Colors.white.withOpacity(0.04),
                            ),
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Container(
                                  width: 58,
                                  height: 58,
                                  decoration: BoxDecoration(
                                    color: Colors.white,
                                    borderRadius: BorderRadius.circular(10),
                                  ),
                                  child: const Icon(
                                    Icons.file_upload_outlined,
                                    color: Color(0xFF1A2E63),
                                    size: 34,
                                  ),
                                ),

                                const SizedBox(height: 20),

                                const Text(
                                  'Tap to upload',
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontSize: 23,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),

                                const SizedBox(height: 20),

                                Text(
                                  'You can upload photos or PDF files',
                                  style: TextStyle(
                                    color: Colors.white.withOpacity(0.65),
                                    fontSize: 16,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),

                        const SizedBox(height: 24),

                        // ------------------------------------------------
                        // Buttons
                        // ------------------------------------------------
                        Row(
                          children: [
                            _uploadButton(
                              icon: Icons.camera_alt_outlined,
                              text: 'Take Photo',
                              onTap: _takePhoto,
                            ),

                            const SizedBox(width: 12),

                            _uploadButton(
                              icon: Icons.image_outlined,
                              text: 'Gallery',
                              onTap: _pickFromGallery,
                            ),

                            const SizedBox(width: 12),

                            _uploadButton(
                              icon: Icons.insert_drive_file_outlined,
                              text: 'File',
                              onTap: _pickFile,
                            ),
                          ],
                        ),

                        const SizedBox(height: 35),

                        // ------------------------------------------------
                        // Files
                        // ------------------------------------------------
                        if (_files.isNotEmpty)
                          SizedBox(
                            height: 110,
                            child: ListView.separated(
                              scrollDirection: Axis.horizontal,
                              itemCount: _files.length + 1,
                              separatorBuilder: (_, __) =>
                                  const SizedBox(width: 16),
                              itemBuilder: (context, index) {
                                if (index == _files.length) {
                                  return _buildAddButton();
                                }

                                return _buildFilePreview(_files[index], index);
                              },
                            ),
                          )
                        else
                          _buildAddButton(),

                        const SizedBox(height: 55),

                        // ------------------------------------------------
                        // Continue
                        // ------------------------------------------------
                        SizedBox(
                          width: double.infinity,
                          height: 72,
                          child: ElevatedButton(
                            onPressed: _continue,
                            style: ElevatedButton.styleFrom(
                              backgroundColor: const Color(0xFF00194D),
                              foregroundColor: Colors.white,
                              elevation: 0,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(40),
                              ),
                            ),
                            child: const Text(
                              'Continue',
                              style: TextStyle(
                                fontSize: 22,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                        ),
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
}
