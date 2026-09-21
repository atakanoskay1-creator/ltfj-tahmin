"""Conservative extraction for Turkish ICAO METARs, not a general decoder."""

import re


def observation_body(raw):
    tokens = raw.upper().strip().rstrip("=").split()
    for i, token in enumerate(tokens):
        if token in {"TEMPO", "BECMG", "NOSIG", "RMK", "PROB30", "PROB40"}:
            return tokens[:i]
    return tokens


def parse(raw, station="LTFJ"):
    tokens = observation_body(raw)
    result = dict(ceiling_ft=None, ceiling_state="unknown", below_500=None,
                  temperature_c=None, dewpoint_c=None, spread_c=None,
                  wind_direction_deg=None, wind_speed_kt=None, wind_gust_kt=None,
                  visibility_m=None, visibility_lower_bound=False, qnh_hpa=None,
                  weather="", corrected="COR" in tokens)
    if (station not in tokens[:3] or "NIL" in tokens
            or not any(re.fullmatch(r"\d{6}Z", token) for token in tokens[:5])):
        return result
    heights, unknown, cloud_seen, clear = [], False, False, False
    for token in tokens:
        cloud = re.fullmatch(r"(FEW|SCT|BKN|OVC|VV)(\d{3}|///)(?:CB|TCU|///)?", token)
        if cloud:
            cover, height = cloud.groups()
            cloud_seen = True
            if cover in {"BKN", "OVC", "VV"}:
                if height == "///":
                    unknown = True
                else:
                    heights.append(int(height) * 100)
        elif (token.startswith(("BKN", "OVC", "VV", "FEW", "SCT"))
              or re.fullmatch(r"/{6,9}(?:CB|TCU)?", token)):
            unknown = True
        if token in {"CAVOK", "NSC", "NCD", "CLR", "SKC"}:
            clear = True
        temp = re.fullmatch(r"(M?\d{2})/(M?\d{2})", token)
        if temp:
            result["temperature_c"], result["dewpoint_c"] = [
                -int(x[1:]) if x.startswith("M") else int(x) for x in temp.groups()]
            result["spread_c"] = result["temperature_c"] - result["dewpoint_c"]
        wind = re.fullmatch(r"(\d{3}|VRB)(\d{2,3})(?:G(\d{2,3}))?KT", token)
        if wind:
            direction, speed, gust = wind.groups()
            result.update(wind_direction_deg=None if direction == "VRB" else int(direction),
                          wind_speed_kt=int(speed), wind_gust_kt=int(gust) if gust else None)
        if re.fullmatch(r"Q\d{4}", token):
            result["qnh_hpa"] = int(token[1:])
        if re.fullmatch(r"\d{4}", token) and result["visibility_m"] is None:
            result["visibility_m"] = 10000 if token == "9999" else int(token)
            result["visibility_lower_bound"] = token == "9999"
        if token == "CAVOK":
            result.update(visibility_m=10000, visibility_lower_bound=True)
    # A definite low layer establishes the event even if another layer is unknown.
    # Its exact minimum ceiling remains unknown if an unmeasured layer exists.
    if heights and min(heights) < 500 and not clear:
        result.update(ceiling_ft=None if unknown else min(heights),
                      ceiling_state="low_with_unknown_layer" if unknown else "measured",
                      below_500=True)
    elif unknown or (clear and heights):
        pass
    elif heights:
        result.update(ceiling_ft=min(heights), ceiling_state="measured", below_500=False)
    elif clear or cloud_seen:
        result.update(ceiling_state="no_ceiling_reported", below_500=False)
    wx = re.compile(r"[+-]?(?:VC)?(?:MI|PR|BC|DR|BL|SH|TS|FZ)?(?:DZ|RA|SN|SG|PL|GR|GS|BR|FG|FU|VA|DU|SA|HZ|SQ|FC|SS|DS)+")
    result["weather"] = " ".join(t for t in tokens if wx.fullmatch(t))
    return result
