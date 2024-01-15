from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Component
from canvas.models import Canvas
from .s3_utils import upload_file_to_s3
from .AI_utils import generate_image
import io
import requests
import datetime
from .nukki import remove_background
from .serializers import ComponentSerializer
from .serializers import TextUploadSerializer
import random
from .recommend import search_pixabay_images
from django.utils import timezone

class BackgroundUploadView(APIView):
    def put(self, request, canvas_id, *args, **kwargs):
        try:
            canvas = Canvas.objects.get(id=canvas_id)
            file = request.FILES.get('file')
            if not file:
                return Response({"message": "업로드할 파일이 없습니다."}, status=status.HTTP_400_BAD_REQUEST)

            component_type = request.data.get('component_type', 'Background')
            component_source = request.data.get('component_source', 'Upload')

            key = f"{canvas_id}/background/{file.name}"
            ExtraArgs = {'ContentType': file.content_type}

            file_url = upload_file_to_s3(file, key, ExtraArgs)
            if not file_url:
                return Response({"message": "S3 버킷에 파일 업로드 실패"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            existing_background = Component.objects.filter(canvas_id=canvas, component_type='Background').first()

            if existing_background:
                existing_background.component_url = file_url
                existing_background.component_source = component_source
                existing_background.created_at = timezone.now()
                existing_background.updated_at = timezone.now()
                existing_background.save()

            else:
                component = Component.objects.create(
                    canvas_id=canvas,
                    component_type=component_type,
                    component_source=component_source,
                    component_url=file_url,
                    position_x=0.0,
                    position_y=0.0
                )

                return Response({
                    "message": "직접 배경 업로드 성공",
                    "result": {
                        "component": {
                            "component_id": component.id,
                            "component_type": component_type,
                            "component_source": component_source
                        }
                    }
                }, status=status.HTTP_201_CREATED)

            return Response({
                "message": "직접 배경 업로드 성공",
                "result": {
                    "component": {
                        "component_id": existing_background.id,
                        "component_type": component_type,
                        "component_source": component_source
                    }
                }
            }, status=status.HTTP_200_OK)
        except Canvas.DoesNotExist:
            return Response({
                "message": "존재하지 않는 캔버스 ID입니다.",
                "result": None
            }, status=status.HTTP_404_NOT_FOUND)

    def get(self, request, canvas_id, *args, **kwargs):
        try:
            canvas_exists = Canvas.objects.filter(id=canvas_id).exists()
            if not canvas_exists:
                return Response({
                    "message": "존재하지 않는 캔버스 ID입니다.",
                    "result": None
                }, status=status.HTTP_404_NOT_FOUND)

            background_components = Component.objects.filter(
                canvas_id=canvas_id,
                component_type='Background',
                component_source='Upload'
            )

            if not background_components:
                return Response({
                    "message": "이 캔버스에 업로드된 배경이 없습니다.",
                    "result": None
                }, status=status.HTTP_404_NOT_FOUND)

            serializer = ComponentSerializer(background_components, many=True)
            return Response({
                "message": "직접 업로드한 배경 조회 성공",
                "result": {"component": serializer.data}
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class BackgroundAIView(APIView):
    def post(self, request, canvas_id, *args, **kwargs):
        try:
            canvas = Canvas.objects.get(id=canvas_id)
            color = request.data.get('color')
            theme = request.data.get('theme')
            place = request.data.get('place')

            if not all([color, theme, place]):
                return Response({"message": "색상, 테마, 장소는 모두 필수입니다."}, status=status.HTTP_400_BAD_REQUEST)

            prompt = f"{color} 색상으로 {theme} 테마의 {place} 이미지를 생성합니다."

            image_type = request.data.get('image_type', 'Background')
            image_count = int(request.data.get('image_count', 3))

            images_urls = generate_image(prompt, image_count, image_type)
            s3_urls = []

            for image_url in images_urls:
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
                file_name = f"{canvas_id}_{timestamp}.png"
                key = f"{canvas_id}/background/{file_name}"
                ExtraArgs = {'ContentType': 'image/jpeg'}
                file_content = requests.get(image_url).content
                s3_url = upload_file_to_s3(io.BytesIO(file_content), key , ExtraArgs)
                s3_urls.append(s3_url)

            return Response({
                "message": "AI 배경 3개 생성 및 S3 버킷 업로드 성공",
                "canvas_id": canvas_id,
                "result": {
                    "s3_urls": s3_urls
                }
            }, status=status.HTTP_201_CREATED)
        except Canvas.DoesNotExist:
            return Response({
                "message": "존재하지 않는 캔버스 ID입니다.",
                "result": None
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class BackgroundSelectView(APIView):
    def put(self, request, canvas_id, *args, **kwargs):
        try:
            canvas = Canvas.objects.get(id=canvas_id)
            selected_url = request.data.get('selected_url')

            if not selected_url:
                return Response({"message": "이미지 URL은 필수입니다."}, status=status.HTTP_400_BAD_REQUEST)

            component_type = request.data.get('component_type', 'Background')
            component_source = request.data.get('component_source', 'AI')

            existing_background = Component.objects.filter(canvas_id=canvas, component_type='Background').first()

            if existing_background:
                existing_background.component_url = selected_url
                existing_background.component_source = component_source
                existing_background.created_at = timezone.now()
                existing_background.updated_at = timezone.now()
                existing_background.save()

                return Response({
                    "message": "선택한 AI 배경 업로드 성공",
                    "result": {
                        "component": {
                            "component_id": existing_background.id,
                            "component_type": component_type,
                            "component_source": component_source
                        }
                    }
                }, status=status.HTTP_200_OK)

            else:
                component = Component.objects.create(
                    canvas_id=canvas,
                    component_type=component_type,
                    component_source=component_source,
                    component_url=selected_url,
                    position_x=0.0,
                    position_y=0.0
                )

                return Response({
                    "message": "선택한 AI 배경 업로드 성공",
                    "result": {
                        "component": {
                            "component_id": component.id,
                            "component_type": component_type,
                            "component_source": component_source
                        }
                    }
                }, status=status.HTTP_201_CREATED)
        except Canvas.DoesNotExist:
            return Response({
                "message": "존재하지 않는 캔버스 ID입니다.",
                "result": None
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class StickerAIView(APIView):
    def post(self, request, canvas_id, *args, **kwargs):
        try:
            canvas = Canvas.objects.get(id=canvas_id)
            describe = request.data.get('describe')
            style = request.data.get('style')

            if not all([describe, style]):
                return Response({"message": "스티커 묘사, 스타일은 모두 필수입니다."}, status=status.HTTP_400_BAD_REQUEST)

            prompt = f"{style} 스타일로 {describe} 이미지를 생성합니다."

            image_type = request.data.get('image_type', 'Sticker')
            image_count = int(request.data.get('image_count', 4))

            images_urls = generate_image(prompt, image_count, image_type)
            s3_urls = []

            for image_url in images_urls:
                processed_image_url = remove_background(image_url)

                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
                file_name = f"{canvas_id}_{timestamp}.png"
                key = f"{canvas_id}/sticker/{file_name}"
                ExtraArgs = {'ContentType': 'image/png'}
                s3_url = upload_file_to_s3(processed_image_url, key, ExtraArgs)
                s3_urls.append(s3_url)

            return Response({
                "message": "AI 스티커 4개 생성 및 S3 버킷 업로드 성공",
                "canvas_id": canvas_id,
                "result": {
                    "s3_urls": s3_urls
                }
            }, status=status.HTTP_201_CREATED)
        except Canvas.DoesNotExist:
            return Response({
                "message": "존재하지 않는 캔버스 ID입니다.",
                "result": None
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class StickerSelectView(APIView):
    def post(self, request, canvas_id, *args, **kwargs):
        try:
            canvas = Canvas.objects.get(id=canvas_id)
            selected_url = request.data.get('selected_url')

            if not selected_url:
                return Response({"message": "이미지 URL은 필수입니다."}, status=status.HTTP_400_BAD_REQUEST)

            component_type = request.data.get('component_type', 'Sticker')
            component_source = request.data.get('component_source', 'AI')

            component = Component.objects.create(
                canvas_id=canvas,
                component_type=component_type,
                component_source=component_source,
                component_url=selected_url,
                position_x=0.0,
                position_y=0.0
            )

            return Response({
                "message": "선택한 AI 스티커 업로드 성공",
                "result": {
                    "component": {
                        "component_id": component.id,
                        "component_type": component_type,
                        "component_source": component_source
                    }
                }
            }, status=status.HTTP_201_CREATED)
        except Canvas.DoesNotExist:
            return Response({
                "message": "존재하지 않는 캔버스 ID입니다.",
                "result": None
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request, canvas_id, *args, **kwargs):
        try:
            canvas_exists = Canvas.objects.filter(id=canvas_id).exists()
            if not canvas_exists:
                return Response({
                    "message": "존재하지 않는 캔버스 ID입니다.",
                    "result": None
                }, status=status.HTTP_404_NOT_FOUND)

            ai_stickers = Component.objects.filter(
                canvas_id=canvas_id,
                component_type='Sticker',
                component_source='AI'
            )

            if not ai_stickers:
                return Response({
                    "message": "이 캔버스에 AI 생성된 스티커가 없습니다.",
                    "result": None
                }, status=status.HTTP_404_NOT_FOUND)

            serializer = ComponentSerializer(ai_stickers, many=True)
            return Response({
                "message": "AI 생성한 스티커 조회 성공",
                "result": {"component": serializer.data}
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TextUploadView(APIView):
    def post(self, request, canvas_id, *args, **kwargs):

        try:
            canvas = Canvas.objects.get(pk=canvas_id)
        except Canvas.DoesNotExist:
            return Response({"message": "캔버스가 존재하지 않습니다."}, status=status.HTTP_404_NOT_FOUND)

        text = request.data.get('component_url')
        component_type = request.data.get('component_type', 'Text')
        component_source = request.data.get('component_source', 'Upload')

        TextComponent = Component(canvas_id=canvas,
                                  component_type=component_type,
                                  component_source=component_source,
                                  component_url=text,
                                  position_x=0.0,
                                  position_y=0.0,
                            )

        serializer = TextUploadSerializer(TextComponent, data=request.data)
        if serializer.is_valid():
            TextComponent.save()
            return Response({"message": "직접 텍스트 업로드 성공",
                                    "result": {
                                        "component": {
                                            "component_id": TextComponent.id,
                                            "component_type" : component_type,
                                            "component_source": component_source,
                                            "component_url": TextComponent.component_url
                                            }
                                        }
                                    }, status=status.HTTP_204_NO_CONTENT)

        return Response({"message": "텍스트 업로드에 실패했습니다.",
                                "result": None
                         }, status=status.HTTP_404_NOT_FOUND)

class ComponentDeleteView(APIView):
    def delete(self, request, component_id, *args, **kwargs):

        try:
            component = Component.objects.get(id=component_id)
            component.delete()
            return Response({"message": "요소 삭제 성공"}, status=status.HTTP_204_NO_CONTENT)

        except Component.DoesNotExist:
            return Response({"message": "요소 삭제에 실패했습니다.",
                             "result": None}, status=status.HTTP_404_NOT_FOUND)

class BackgroundRecommendView(APIView):
    def get(self, request, *args, **kwargs):
        images_urls = []
        all_keywords = ['nature', 'city', 'ocean', 'forest', 'mountains', 'animals', 'space',
                        'cars', 'seasons', 'house', 'room', 'factory', 'daily', 'cafe',
                        'comfortable', 'christmas', 'furniture', 'library', 'color', 'animation']

        for _ in range(10):
            random_keyword = random.choice(all_keywords)
            image_results = search_pixabay_images(random_keyword)

            if image_results and image_results['hits']:
                images_urls.append(image_results['hits'][0]['largeImageURL'])
                all_keywords.remove(random_keyword)

        if images_urls:
            return Response({
                "message": "배경 추천 성공",
                "results": images_urls
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                "message": "배경 추천 실패",
                "result": None
            }, status=status.HTTP_404_NOT_FOUND)