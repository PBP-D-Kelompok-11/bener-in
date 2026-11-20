from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import AccountSerializer, LoginSerializer


@api_view(['GET'])
@permission_classes([AllowAny])
def csrf_token(request):
    return Response(
        {'csrf_token': get_token(request)},
        headers={'Cache-Control': 'no-store'},
    )


@method_decorator(csrf_protect, name='dispatch')
class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        credentials = LoginSerializer(data=request.data)
        credentials.is_valid(raise_exception=True)
        user = authenticate(request, **credentials.validated_data)
        if user is None:
            return Response(
                {'detail': 'Username atau kata sandi salah.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        login(request, user)
        return Response(
            {'user': AccountSerializer(user).data, 'csrf_token': get_token(request)},
            headers={'Cache-Control': 'no-store'},
        )


@api_view(['GET'])
def me(request):
    return Response(
        AccountSerializer(request.user).data,
        headers={'Cache-Control': 'no-store'},
    )


@api_view(['POST'])
def sign_out(request):
    logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)
