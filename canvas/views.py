from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from user.models import User
from .models import Canvas, CanvasMember
from .serializers import CanvasSerializer, CanvasPersonalListSerializer

class CanvasCreateView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = CanvasSerializer(data=request.data)

        if serializer.is_valid():
            canvas=serializer.save()
            return Response({
                    "message": "캔버스 생성 성공하였습니다.",
                    "canvas_name":serializer.data["canvas_name"],
                    "canvas_id": canvas.id
                }, status = status.HTTP_201_CREATED)
        return Response({"message": "캔버스 생성 실패했습니다."}, status = status.HTTP_404_NOT_FOUND)

class CanvasUpdateDeleteView(APIView):

    def put(self, request, canvas_id, *args, **kwargs):
        canvas_name= request.data.get("canvas_name")

        try:
            canvas = Canvas.objects.get(id=canvas_id)
            canvas.canvas_name = canvas_name
            canvas.updated_at= timezone.now()
            canvas.save()
            return Response({"message": "캔버스 이름 수정 성공하였습니다."},status = status.HTTP_200_OK)
        except Canvas.DoesNotExist:
            return Response({"message": "캔버스 이름 수정 실패하였습니다."},status = status.HTTP_404_NOT_FOUND)

    def delete(self, request, canvas_id, *args, **kwargs):
        try:
            canvas = Canvas.objects.get(id=canvas_id)
            canvas.delete()
            canvas.deleted_at = timezone.now()
            return Response({"message": "캔버스 삭제 성공하였습니다."},status = status.HTTP_200_OK)
        except Canvas.DoesNotExist:
            return Response({"message": "캔버스 삭제 실패하였습니다."},status = status.HTTP_404_NOT_FOUND)


class MemberInvite(APIView):

    def post(self, request, canvas_id):

        user_email = request.data.get('user_email')

        try:
            user = User.objects.get(user_email=user_email)
        except User.DoesNotExist:
            return Response({'message': '해당 유저가 존재하지 않습니다.',
                            'result': None}, status=status.HTTP_404_NOT_FOUND)

        try:
            canvas = Canvas.objects.get(pk=canvas_id)
        except Canvas.DoesNotExist:
            return Response({'message': '해당 캔버스가 존재하지 않습니다.',
                            'result': None}, status=status.HTTP_404_NOT_FOUND)

        try:
            CanvasMember.objects.get(member_id=user.id)
        except CanvasMember.DoesNotExist:
            canvasmember = CanvasMember(
                canvas_id=canvas,
                member_id=user.id,
                created_at=timezone.now(),
                updated_at=timezone.now(),
                deleted_at=None
            )
            canvasmember.save()

            return Response({'message': "친구 초대 성공",
                                 'result': {
                                     'user_email': user.user_name}}, status=status.HTTP_204_NO_CONTENT)
        return Response({'message': '친구 초대에 실패했습니다.',
                                 'result': None}, status=status.HTTP_404_NOT_FOUND)

class CanvasPersonalListView(APIView):
    def get(self, request, user_id):
        canvases = Canvas.objects.filter(owner_id=user_id)
        serializer = CanvasPersonalListSerializer(canvases, many=True)

        canvas_list = []
        for canvas in canvases:
            canvas_data = {
                "canvas_id": canvas.id,
                "canvas_preview_url": canvas.canvas_preview_url,
                "canvas_name": canvas.canvas_name,
                "update_at": canvas.updated_at,
            }
            canvas_list.append(canvas_data)

        return Response({
            "message": "개인 캔버스 전체 조회 성공",
            "result": {
                "canvases": canvas_list
            }
        }, status=status.HTTP_200_OK)