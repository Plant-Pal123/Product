"""The Sentinel Hub evalscript run server-side to compute NDVI per pixel.

NDVI = (B08 - B04) / (B08 + B04), the standard red/near-infrared vegetation
index. Pixels are masked out using the Sentinel-2 L2A Scene Classification
Layer (SCL) so cloud, cloud shadow, snow and no-data pixels don't pull the
mean toward nonsense values - the Statistical API's `dataMask` output is
exactly what excludes them from the returned mean/stDev/sampleCount.

SCL classes excluded: 0 (no data), 1 (saturated/defective), 3 (cloud shadow),
8/9 (cloud medium/high probability), 10 (thin cirrus), 11 (snow/ice).
Per https://docs.sentinel-hub.com/api/latest/data/sentinel-2-l2a/ - #Scene
classification layer.
"""

NDVI_EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: [{ bands: ["B04", "B08", "SCL", "dataMask"] }],
    output: [
      { id: "ndvi", bands: 1, sampleType: "FLOAT32" },
      { id: "dataMask", bands: 1 }
    ]
  };
}

const EXCLUDED_SCL = [0, 1, 3, 8, 9, 10, 11];

function evaluatePixel(samples) {
  let ndvi = (samples.B08 - samples.B04) / (samples.B08 + samples.B04);
  let masked = samples.dataMask * (EXCLUDED_SCL.includes(samples.SCL) ? 0 : 1);
  return {
    ndvi: [ndvi],
    dataMask: [masked],
  };
}
"""
