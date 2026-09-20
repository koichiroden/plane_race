# -*- coding: utf-8 -*-
"""共通の地図投影ロジック(簡易正距円筒図法 + 経度をcos(lat)で補正)"""
import math

CANVAS_W = 1080
CANVAS_H = 1920

# リール/ショート動画のUI(キャプション・アイコン等)が上下にかぶる
# 「セーフゾーン」。縦方向に8分割した時の一番上・一番下の1区画
# (それぞれ CANVAS_H/8 = 240px)には、タイトルとプログレスバーを
# 一切入れないようにする。地図(路線・駅)自体はこの区画にはみ出しても
# 構わないが、タイトル/凡例(render_base.py)とスコアボード(animate.py)
# はこの定数を基準に、必ず内側に収まるよう計算する。
SAFE_ZONE_PX = CANVAS_H // 8       # 240
SAFE_TOP_Y = SAFE_ZONE_PX          # 240: タイトルはこれより下に
SAFE_BOTTOM_Y = CANVAS_H - SAFE_ZONE_PX  # 1680: プログレスバーはこれより上に

# 地図を描画する領域(上部はタイトル、下部はスコアボード分を空ける)
MAP_TOP = 470
MAP_BOTTOM = 1540
MAP_LEFT = 60
MAP_RIGHT = 1020


def compute_projection(all_coords, pad_ratio=0.16, stretch_to_fit=False, max_stretch=1.6):
    """all_coords がちょうど収まる投影パラメータを計算する。

    stretch_to_fit=False(既定): 従来通り、縦横比を保ったまま
    avail_w/avail_h に収まる最大の縮尺(min)を使う。どちらかの軸に
    余白が残る(レターボックス状になる)ことがある。

    stretch_to_fit=True: 縦横比を保たず、x軸・y軸それぞれ独立に
    avail_w/avail_h いっぱいまで拡大しようとする。経路の形が東西・南北
    どちらかに極端に偏っている(例: 東京〜福岡のようにほぼ東西一直線)
    場合でも、縦長キャンバスの余白に遠方の地形(北海道・沖縄など)が
    写り込むのを防ぎ、出発地・到着地が画角にしっかり収まるようにする。
    ただし完全に引き伸ばすと海岸線の形が不自然に歪むため、余白の少ない
    軸(基準)を基準に、もう一方の軸の拡大率は最大 max_stretch 倍までに
    制限する(それでも収まりきらない分だけ、従来通り余白として残る)。
    """
    lons = [c[0] for c in all_coords]
    lats = [c[1] for c in all_coords]
    lon_min, lon_max = min(lons), max(lons)
    lat_min, lat_max = min(lats), max(lats)
    lat0 = (lat_min + lat_max) / 2
    cos0 = math.cos(math.radians(lat0))

    def to_plane(lon, lat):
        x = (lon - lon_min) * cos0
        y = (lat_max - lat)
        return x, y

    xs, ys = [], []
    for lon, lat in all_coords:
        x, y = to_plane(lon, lat)
        xs.append(x)
        ys.append(y)
    x_span = max(xs) - min(xs)
    y_span = max(ys) - min(ys)
    x_min, y_min = min(xs), min(ys)

    pad_x = x_span * pad_ratio
    pad_y = y_span * pad_ratio
    x_span_p = x_span + 2 * pad_x
    y_span_p = y_span + 2 * pad_y

    avail_w = MAP_RIGHT - MAP_LEFT
    avail_h = MAP_BOTTOM - MAP_TOP

    if stretch_to_fit and x_span_p and y_span_p:
        scale_x_raw = avail_w / x_span_p
        scale_y_raw = avail_h / y_span_p
        scale_uniform = min(scale_x_raw, scale_y_raw)
        cap = scale_uniform * max_stretch
        scale_x = min(scale_x_raw, cap)
        scale_y = min(scale_y_raw, cap)
    else:
        scale = min(avail_w / x_span_p, avail_h / y_span_p) if x_span_p and y_span_p else 1.0
        scale_x = scale_y = scale

    draw_w = x_span_p * scale_x
    draw_h = y_span_p * scale_y
    off_x = MAP_LEFT + (avail_w - draw_w) / 2
    off_y = MAP_TOP + (avail_h - draw_h) / 2

    return {
        "lon_min": lon_min, "lat_max": lat_max, "cos0": cos0,
        "x_min": x_min - pad_x, "y_min": y_min - pad_y,
        "scale_x": scale_x, "scale_y": scale_y, "off_x": off_x, "off_y": off_y,
    }


# 日本全国を(北海道〜沖縄まで)常に同じ縮尺で表示したい場合に使う固定範囲。
# 東京-福岡のような広域(新幹線・飛行機)ルートで、ルートだけに合わせて
# ズームすると海岸線データとの整合が取りにくくなる/回ごとに縮尺が変わって
# しまうのを避けるため、この固定範囲を使うと、はみ出した地域は自然に
# フレームアウトする(=拡大縮小はせず、常に同じ地図の上にルートを乗せる)。
JAPAN_BBOX = {"lon_min": 122.5, "lon_max": 153.5, "lat_min": 24.0, "lat_max": 45.8}


def compute_fixed_projection(bbox=None, pad_ratio=0.02):
    """compute_projection() と互換の辞書を、ルートではなく固定の緯度経度範囲
    (既定: 日本全国, JAPAN_BBOX)から作る。route側の座標がこの範囲の外に
    出ても、拡大縮小はせずそのままフレーム外に切れる。"""
    bbox = bbox or JAPAN_BBOX
    corner_coords = [
        (bbox["lon_min"], bbox["lat_min"]), (bbox["lon_max"], bbox["lat_min"]),
        (bbox["lon_min"], bbox["lat_max"]), (bbox["lon_max"], bbox["lat_max"]),
    ]
    return compute_projection(corner_coords, pad_ratio=pad_ratio)


def compute_route_fit_projection(all_coords, pad_ratio=0.22, min_span_deg=1.4):
    """全国版(map_extent="japan")用: 日本全体の固定範囲ではなく、実際の
    出発地・到着地・経路(all_coords)がちょうど収まるように毎回ズーム
    レベルを計算する。東京〜札幌のような遠距離ペアは自然に広い画角、
    東京〜前橋のような近距離ペアは自然に寄った画角になる。

    経路がほぼ一直線(緯度・経度どちらかの幅がとても狭い)だと極端な
    ズームイン/歪みになってしまうため、min_span_deg 未満の幅は中心を
    基準に min_span_deg まで広げてから使う。

    また、東京〜福岡のように経路がほぼ東西一直線(縦長キャンバスとは
    逆の向き)の場合、縦横比を保ったまま(letterbox)フィットさせると
    上下に大きな余白ができ、そこに北海道や沖縄など無関係な地形が写り
    込んで「引き気味」に見えてしまう。これを避けるため、
    stretch_to_fit=True(縦横比を保たない、x軸・y軸独立フィット)を
    使い、出発地・到着地が画角いっぱいに収まるようにしている。
    """
    lons = [c[0] for c in all_coords]
    lats = [c[1] for c in all_coords]
    lon_min, lon_max = min(lons), max(lons)
    lat_min, lat_max = min(lats), max(lats)

    if lon_max - lon_min < min_span_deg:
        cx = (lon_min + lon_max) / 2
        lon_min, lon_max = cx - min_span_deg / 2, cx + min_span_deg / 2
    if lat_max - lat_min < min_span_deg:
        cy = (lat_min + lat_max) / 2
        lat_min, lat_max = cy - min_span_deg / 2, cy + min_span_deg / 2

    corner_coords = [
        (lon_min, lat_min), (lon_max, lat_min),
        (lon_min, lat_max), (lon_max, lat_max),
    ]
    return compute_projection(corner_coords, pad_ratio=pad_ratio, stretch_to_fit=True)


def project(params, lon, lat):
    x = (lon - params["lon_min"]) * params["cos0"]
    y = (params["lat_max"] - lat)
    px = (x - params["x_min"]) * params["scale_x"] + params["off_x"]
    py = (y - params["y_min"]) * params["scale_y"] + params["off_y"]
    return px, py


def unproject(params, px, py):
    """project() の逆変換。画面上のある範囲(例: キャンバス+余白)が
    実際の経度緯度でどこに当たるかを知りたい時に使う
    (例: 海岸線データを表示範囲だけに間引く)。"""
    x = (px - params["off_x"]) / params["scale_x"] + params["x_min"]
    y = (py - params["off_y"]) / params["scale_y"] + params["y_min"]
    lon = x / params["cos0"] + params["lon_min"]
    lat = params["lat_max"] - y
    return lon, lat
