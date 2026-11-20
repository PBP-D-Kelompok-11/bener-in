from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.models import Customer, MitraReparasi
from locations.services import nearby_mitra
from repair.models import RepairRequest
from reviews.impact import get_impact_summary

from .serializers import (
    AccountSerializer,
    ImpactSummarySerializer,
    LoginSerializer,
    MitraSerializer,
    NearbyMitraQuerySerializer,
    RepairSerializer,
)


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


@api_view(['GET'])
def repair_list(request):
    user = request.user
    repairs = RepairRequest.objects.select_related('mitra')
    if isinstance(user, Customer):
        repairs = repairs.filter(customer=user)
    elif isinstance(user, MitraReparasi):
        repairs = repairs.filter(mitra=user)
    else:
        raise PermissionDenied()

    latest = repairs.order_by('-created_at', '-pk')[:50]
    return Response(
        {'results': RepairSerializer(latest, many=True).data},
        headers={'Cache-Control': 'no-store'},
    )


@api_view(['GET'])
@permission_classes([AllowAny])
def mitra_detail(request, pk):
    mitra = get_object_or_404(MitraReparasi, pk=pk, is_active=True)
    return Response(MitraSerializer(mitra, context={'request': request}).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def mitra_nearby(request):
    query = NearbyMitraQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    try:
        nearby = nearby_mitra(**query.validated_data)
    except ValueError as exc:
        raise ValidationError({'detail': str(exc)}) from exc

    results = [
        {
            **MitraSerializer(mitra, context={'request': request}).data,
            'distance_km': round(distance, 2),
        }
        for distance, mitra in nearby
    ]
    return Response({'results': results})


@api_view(['GET'])
def impact_summary(request):
    if not isinstance(request.user, Customer):
        raise PermissionDenied()

    completed = RepairRequest.objects.filter(
        customer=request.user,
        status=RepairRequest.Status.COMPLETED,
    ).count()
    return Response(
        ImpactSummarySerializer(get_impact_summary(completed)).data,
        headers={'Cache-Control': 'no-store'},
    )
