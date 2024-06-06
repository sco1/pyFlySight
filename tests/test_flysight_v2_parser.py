from textwrap import dedent

import polars
import pytest

from pyflysight.flysight_proc import (
    FlysightV2,
    SensorInfo,
    _calculate_derived_columns,
    _parse_header,
    _partition_sensor_data,
    _raw_data_to_dataframe,
    _split_v2_sensor_data,
)

SAMPLE_SPLIT_FILE = dedent(
    """\
    $UNIT,VBAT,s,volt
    $DATA
    $IMU,59970.376,-0.427,1.770,1.953,-0.01464,-0.00732,0.94287,25.64
    """
).splitlines()


def test_data_split() -> None:
    header, data = _split_v2_sensor_data(SAMPLE_SPLIT_FILE)
    assert header == ["$UNIT,VBAT,s,volt"]
    assert data == ["$IMU,59970.376,-0.427,1.770,1.953,-0.01464,-0.00732,0.94287,25.64"]


def test_data_split_no_partition_raises() -> None:
    with pytest.raises(ValueError, match="HELLO"):
        _ = _split_v2_sensor_data(SAMPLE_SPLIT_FILE, partition_keyword="$HELLO")


SAMPLE_HEADER_ONE_SENSOR = dedent(
    """\
    $FLYS,1
    $VAR,FIRMWARE_VER,v2023.09.22
    $VAR,DEVICE_ID,003f0033484e501420353131
    $VAR,SESSION_ID,7e67d0e71a53d9d6486b0114
    $COL,BARO,time,pressure,temperature
    $UNIT,BARO,s,Pa,deg C
    """
).splitlines()

TRUTH_SENSOR_INFO = SensorInfo(
    columns=["time", "pressure", "temperature"],
    units=["s", "Pa", "deg C"],
    id_="BARO",
)


def test_header_parse_one_sensor() -> None:
    flysight = _parse_header(SAMPLE_HEADER_ONE_SENSOR)
    assert flysight.firmware_version == "v2023.09.22"
    assert flysight.device_id == "003f0033484e501420353131"
    assert flysight.session_id == "7e67d0e71a53d9d6486b0114"

    assert "BARO" in flysight.sensor_info
    assert flysight.sensor_info["BARO"] == TRUTH_SENSOR_INFO


SAMPLE_HEADER_NO_FIRMWARE = dedent(
    """\
    $FLYS,1
    $VAR,DEVICE_ID,003f0033484e501420353131
    $VAR,SESSION_ID,7e67d0e71a53d9d6486b0114
    """
).splitlines()


def test_header_missing_firmware_raises() -> None:
    with pytest.raises(ValueError, match="firmware"):
        _parse_header(SAMPLE_HEADER_NO_FIRMWARE)


SAMPLE_HEADER_NO_DEVICE_ID = dedent(
    """\
    $FLYS,1
    $VAR,FIRMWARE_VER,v2023.09.22
    $VAR,SESSION_ID,7e67d0e71a53d9d6486b0114
    """
).splitlines()


def test_header_missing_device_raises() -> None:
    with pytest.raises(ValueError, match="device"):
        _parse_header(SAMPLE_HEADER_NO_DEVICE_ID)


SAMPLE_HEADER_NO_SESSION_ID = dedent(
    """\
    $FLYS,1
    $VAR,FIRMWARE_VER,v2023.09.22
    $VAR,DEVICE_ID,003f0033484e501420353131
    """
).splitlines()


def test_header_missing_session_raises() -> None:
    with pytest.raises(ValueError, match="session"):
        _parse_header(SAMPLE_HEADER_NO_SESSION_ID)


SAMPLE_HEADER_MISMATCHED_SENSOR_INFO = dedent(
    """\
    $FLYS,1
    $VAR,FIRMWARE_VER,v2023.09.22
    $VAR,DEVICE_ID,003f0033484e501420353131
    $VAR,SESSION_ID,7e67d0e71a53d9d6486b0114
    $COL,BARO,time,pressure,temperature
    """
).splitlines()


def test_header_partial_missing_sensor_info_raises() -> None:
    with pytest.raises(ValueError, match="lacks column or unit information"):
        _parse_header(SAMPLE_HEADER_MISMATCHED_SENSOR_INFO)


SAMPLE_HEADER_GNSS_INFO = dedent(
    """\
    $FLYS,1
    $VAR,FIRMWARE_VER,v2023.09.22
    $VAR,DEVICE_ID,003f0033484e501420353131
    $VAR,SESSION_ID,7e67d0e71a53d9d6486b0114
    $COL,GNSS,time,lat,lon,hMSL,velN,velE,velD,hAcc,vAcc,sAcc,numSV
    $UNIT,GNSS,,deg,deg,m,m/s,m/s,m/s,m,m,m/s,
    """
).splitlines()


def test_header_gnss_datetime_unit_fill() -> None:
    flysight = _parse_header(SAMPLE_HEADER_GNSS_INFO)
    assert "datetime" in flysight.sensor_info["GNSS"].units


SAMPLE_SENSOR_DATA_SINGLE_LINES = dedent(
    """\
    $IMU,1,2,3,4
    $BARO,5,6,7,8
    """
).splitlines()


def test_sensor_data_partition() -> None:
    sensor_data, initial_timestamp = _partition_sensor_data(SAMPLE_SENSOR_DATA_SINGLE_LINES)

    assert initial_timestamp == pytest.approx(1)

    assert not (sensor_data.keys() - {"IMU", "BARO"})

    assert len(sensor_data["IMU"]) == 1
    assert sensor_data["IMU"][0] == pytest.approx([1, 2, 3, 4])

    assert len(sensor_data["BARO"]) == 1
    assert sensor_data["BARO"][0] == pytest.approx([5, 6, 7, 8])


SAMPLE_SENSOR_DATA_MULTI_LINES = dedent(
    """\
    $IMU,1,2
    $BARO,3,4
    $IMU,5,6
    """
).splitlines()


def test_sensor_data_partition_multi_line() -> None:
    sensor_data, _ = _partition_sensor_data(SAMPLE_SENSOR_DATA_MULTI_LINES)
    assert not (sensor_data.keys() - {"IMU", "BARO"})

    assert len(sensor_data["IMU"]) == 2
    assert sensor_data["IMU"][0] == pytest.approx([1, 2])
    assert sensor_data["IMU"][1] == pytest.approx([5, 6])

    assert len(sensor_data["BARO"]) == 1
    assert sensor_data["BARO"][0] == pytest.approx([3, 4])


DEVICE_INFO_NO_TIMESTAMP = FlysightV2(
    firmware_version="abc123",
    device_id="abc123",
    session_id="abc123",
    sensor_info={"BARO": TRUTH_SENSOR_INFO},
)

SAMPLE_GROUPED_DATA = {"BARO": [[1.0, 2.0, 3.0]]}


def test_dataframe_conversion_no_timestamp_raises() -> None:
    with pytest.raises(ValueError, match="timestamp"):
        _raw_data_to_dataframe(SAMPLE_GROUPED_DATA, DEVICE_INFO_NO_TIMESTAMP)


DEVICE_INFO_WITH_TIMESTAMP = FlysightV2(
    firmware_version="abc123",
    device_id="abc123",
    session_id="abc123",
    sensor_info={"BARO": TRUTH_SENSOR_INFO},
    first_timestamp=0.5,
)


def test_dataframe_conversion_mismatch_column_headers_raises() -> None:
    sample_data = {"BARO": [[1.0, 2.0, 3.0, 4.0]]}
    with pytest.raises(ValueError, match="Number of column headers"):
        _raw_data_to_dataframe(sample_data, DEVICE_INFO_WITH_TIMESTAMP)


def test_dataframe_conversion_no_column_headers_raises() -> None:
    sample_data = {"abcd": [[1.0, 2.0, 3.0]]}
    with pytest.raises(ValueError, match="Could not locate"):
        _raw_data_to_dataframe(sample_data, DEVICE_INFO_WITH_TIMESTAMP)


def test_dataframe_elapsed_time_derived() -> None:
    parsed_sensor_data = _raw_data_to_dataframe(SAMPLE_GROUPED_DATA, DEVICE_INFO_WITH_TIMESTAMP)
    df = parsed_sensor_data["BARO"]

    assert "elapsed_time" in df.columns
    assert df.select(polars.col("elapsed_time").first()).item() == pytest.approx(0.5)


def test_dataframe_pressure_altitude_from_baro() -> None:
    parsed_sensor_data = _raw_data_to_dataframe(SAMPLE_GROUPED_DATA, DEVICE_INFO_WITH_TIMESTAMP)
    df = parsed_sensor_data["BARO"]

    assert "press_alt_m" in df.columns
    assert df.select(polars.col("press_alt_m").first()).item() == pytest.approx(38_754.55)

    assert "press_alt_ft" in df.columns
    assert df.select(polars.col("press_alt_ft").first()).item() == pytest.approx(127_145.96)


def test_dataframe_no_derived_passthrough() -> None:
    # Just need a dummy df for this, passthrough shouldn't need any specific device info
    df = polars.DataFrame({"a": [1, 2], "b": [3, 4]})
    passthrough = _calculate_derived_columns(df, "abcd", DEVICE_INFO_WITH_TIMESTAMP)
    polars.testing.assert_frame_equal(df, passthrough)