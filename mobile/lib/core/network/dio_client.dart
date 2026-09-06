import 'package:dio/dio.dart';

import '../constant/api_constants.dart';

class DioClient {
  DioClient._();

  static final DioClient instance = DioClient._();

  late final Dio dio = _createDio();

  Dio _createDio() {
    return Dio(
      BaseOptions(
        baseUrl: ApiConstants.baseUrl,
        connectTimeout: const Duration(seconds: 15),
        sendTimeout: const Duration(seconds: 15),
        receiveTimeout: const Duration(seconds: 15),
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      ),
    );
  }
}// dio client