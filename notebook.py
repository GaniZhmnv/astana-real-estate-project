import marimo

__generated_with = "0.23.15"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import plotly.express as px
    df = pd.read_csv("astana_real_estate_dataset.csv")
    mo.md(f"### Обзор датасета\n Всего записей: **{len(df)}**")
    df.info()
    df.describe()
    return df, pd, px


@app.cell
def _(df):
    df_feat = df.copy()

    # 1. Очищаем названия районов (оставляем только само название до слова "район")
    df_feat['district'] = df_feat['district'].str.replace(' район, Астана, Казахстан', '', regex=False)

    # 2. Считаем стоимость за 1 м²
    df_feat['price_per_m2'] = df_feat['price'] / df_feat['area_m2']

    # 3. Переименуем колонку с кириллицей
    df_feat = df_feat.rename(columns={'Год постройки': 'build_year'})

    # 4. Вычисляем возраст дома
    df_feat['house_age'] = 2026 - df_feat['build_year']

    # 5. Флаги этажности
    df_feat['is_first_floor'] = (df_feat['current_floor'] == 1).astype(int)
    df_feat['is_last_floor'] = (df_feat['current_floor'] == df_feat['total_floors']).astype(int)

    df_feat[['district', 'price_per_m2', 'house_age', 'is_first_floor', 'is_last_floor']].head()
    return (df_feat,)


@app.cell
def _(df_feat, pd):
    # 1. Функция определения реального района по координатам
    def get_real_district(lat, lon):
        if pd.isna(lat) or pd.isna(lon) or lat == 0 or lon == 0:
            return "Неизвестно"
        if lat < 51.15:
            return "Нуринский" if lon < 71.42 else "Есильский"
        else:
            if lon < 71.41:
                return "Сарыаркинский"
            elif lon > 71.47:
                return "Алматинский"
            else:
                return "Байконурский"

    df_feat['real_district'] = df_feat.apply(
        lambda row: get_real_district(row['apartment_lat'], row['apartment_lon']), 
        axis=1
    )

    # 2. Очищаем название ЖК
    df_feat['rc_clean'] = df_feat['residential_complex'].apply(
        lambda x: "Не указан" if str(x).strip().lower() in ['none', 'nan', '', 'не указан'] else x
    )

    # 3. Умная подпись района (сворачивает дубли)
    def format_district_info(row):
        real = row['real_district']
        declared = row['district']
        if real == declared or declared == "Неизвестно":
            return real
        else:
            return f"{real} (в объявлении: {declared})"

    df_feat['district_display'] = df_feat.apply(format_district_info, axis=1)

    # 4. Считаем медианную цену за м² для каждого реального района
    district_medians = df_feat.groupby('real_district')['price_per_m2'].transform('median')

    # 5. Считаем отклонение цены квартиры от медианы района в %
    diff_pct = ((df_feat['price_per_m2'] - district_medians) / district_medians) * 100

    # Форматируем красивую подпись: например, "-12.5% от медианы" или "+8.0% от медианы"
    df_feat['price_vs_district'] = diff_pct.apply(
        lambda x: f" +{x:.1f}% от средней по району" if x >= 0 else f" {x:.1f}% от средней по району"
    )
    return


@app.cell
def _(df_feat, px):
    # Создаем интерактивный Boxplot
    fig = px.box(
        df_feat, 
        x='district', 
        y='price_per_m2',
        color='district',
        title='<b>Распределение стоимости 1 м² по районам Астаны</b>',
        labels={'district': 'Район', 'price_per_m2': 'Цена за 1 м² (₸)'},
        hover_data=['rooms', 'area_m2', 'price']
    )

    # Настраиваем отображение: ограничиваем ось Y до 1.5 млн ₸ за м², чтобы выбросы не плющили графики
    fig.update_layout(
        xaxis_tickangle=-15,
        showlegend=False,
        height=550,
        yaxis_range=[0, 1500000]
    )

    fig
    return


@app.cell
def _(df_feat):
    # Агрегируем данные по районам
    district_stats = df_feat.groupby('district').agg(
        count=('price', 'count'),
        median_price_m2=('price_per_m2', lambda x: int(x.median())),
        median_total_price=('price', lambda x: int(x.median())),
        avg_area=('area_m2', 'mean'),
        avg_house_age=('house_age', 'mean')
    ).reset_index().sort_values(by='median_price_m2', ascending=False)

    # Красиво форматируем вывод
    district_stats
    return


@app.cell
def _(df_feat, px):
    # Интерактивная карта с отображением сравнения цен
    fig_map = px.scatter_mapbox(
        df_feat[df_feat['price_per_m2'] < 1500000],  # фильтр от диких выбросов
        lat='apartment_lat',
        lon='apartment_lon',
        color='price_per_m2',
        size='area_m2',
        color_continuous_scale='Viridis',
        size_max=12,
        zoom=10.8,
        center={"lat": 51.15, "lon": 71.44},  # Центр Астаны
        hover_name='rc_clean',                 # В шапке плашки — Название ЖК
        hover_data={
            'district_display': True,   # Район (и заявленный, если не совпал)
            'price_vs_district': True,  # <--- ОТКЛОНЕНИЕ ОТ СРЕДНЕЙ ЦЕНЫ РАЙОНА
            'price': ':.0f',            # Итоговая цена
            'price_per_m2': ':.0f',     # Цена за м²
            'rooms': True,              # Комнаты
            'area_m2': True,            # Площадь
            'apartment_lon': False,
            'apartment_lat': False
        },
        labels={
            'rc_clean': 'ЖК',
            'district_display': 'Район',
            'price_vs_district': 'Разница цены ',
            'price': 'Цена (₸)',
            'price_per_m2': 'Цена за м² (₸)',
            'rooms': 'Комнат',
            'area_m2': 'Площадь (м²)'
        },
        title='<b>Карта квартир Астаны: Аналитика цен, ЖК и районов</b>'
    )

    fig_map.update_layout(
        mapbox_style="carto-positron",
        height=650,
        margin={"r": 0, "t": 40, "l": 0, "b": 0}
    )

    fig_map
    return


@app.cell
def _(df_feat, px):
    # Тепловая карта (Heatmap) средних цен: Комнаты vs Тип дома
    pivot_price = df_feat.pivot_table(
        index='rooms', 
        columns='building_type', 
        values='price_per_m2', 
        aggfunc='median'
    )

    fig_heatmap = px.imshow(
        pivot_price,
        labels=dict(x="Тип дома", y="Кол-во комнат", color="Медиана ₸/м²"),
        title="<b>Матрица цен за м²: Комнаты vs Материал дома</b>",
        text_auto=".0f"
    )

    fig_heatmap
    return


if __name__ == "__main__":
    app.run()
