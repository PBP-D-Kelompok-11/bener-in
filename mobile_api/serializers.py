from rest_framework import serializers

from authentication.models import KategoriBarang, MitraReparasi
from repair.models import RepairRequest


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class AccountSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='pk')
    username = serializers.CharField()
    nama_lengkap = serializers.CharField()
    role = serializers.CharField()


class RepairSerializer(serializers.ModelSerializer):
    mitra_id = serializers.IntegerField(read_only=True)
    mitra_name = serializers.CharField(source='mitra.nama_usaha', read_only=True)

    class Meta:
        model = RepairRequest
        fields = (
            'id', 'category', 'item_name', 'description', 'status',
            'mitra_id', 'mitra_name', 'created_at', 'updated_at',
        )


class MitraSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='nama_usaha')
    address = serializers.CharField(source='alamat')
    lat = serializers.FloatField(source='latitude')
    lng = serializers.FloatField(source='longitude')
    phone = serializers.SerializerMethodField()

    class Meta:
        model = MitraReparasi
        fields = ('id', 'name', 'address', 'layanan', 'lat', 'lng', 'phone')

    def get_phone(self, mitra):
        return mitra.no_hp if self.context['request'].user.is_authenticated else ''


class NearbyMitraQuerySerializer(serializers.Serializer):
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lng = serializers.FloatField(min_value=-180, max_value=180)
    radius_km = serializers.FloatField(max_value=100, default=10)
    category = serializers.ChoiceField(choices=KategoriBarang.choices, required=False)


class BadgeSerializer(serializers.Serializer):
    name = serializers.CharField()
    min = serializers.IntegerField()
    unlocked = serializers.BooleanField()


class ImpactSummarySerializer(serializers.Serializer):
    saved_count = serializers.IntegerField()
    badges = BadgeSerializer(many=True)
    current_badge = BadgeSerializer(allow_null=True)
    next_badge = BadgeSerializer(allow_null=True)
    progress_percent = serializers.IntegerField()
    remaining = serializers.IntegerField()
