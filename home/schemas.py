from rest_framework import serializers


class HomeWeatherSerializer(serializers.Serializer):
    tmax = serializers.FloatField(allow_null=True)
    tmin = serializers.FloatField(allow_null=True)
    pop_max = serializers.IntegerField(allow_null=True)
    has_rain = serializers.BooleanField()


class HomeRecentAvgSerializer(serializers.Serializer):
    made_avg = serializers.FloatField(allow_null=True)
    left_avg = serializers.FloatField(allow_null=True)


class HomeWeeklyMadeSerializer(serializers.Serializer):
    date = serializers.DateField()
    made_total = serializers.IntegerField()


class HomeSerializer(serializers.Serializer):
    date = serializers.DateField()
    is_open_today = serializers.BooleanField(help_text="오늘이 가게 휴무 요일이면 false")
    weather = HomeWeatherSerializer(allow_null=True, help_text="날씨 정보가 없으면 null")
    is_holiday = serializers.BooleanField()
    recent_avg = serializers.DictField(
        child=HomeRecentAvgSerializer(),
        help_text="최근 4주 같은 요일의 품목별 평균. 키는 품목 id",
    )
    weekly_made = HomeWeeklyMadeSerializer(many=True, help_text="오늘 포함 최근 7일의 일별 총 생산량")