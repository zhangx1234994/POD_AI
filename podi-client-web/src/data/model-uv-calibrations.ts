export type ModelUvCalibration = {
  materialSlot: string;
  uMin: number;
  uMax: number;
  vMin: number;
  vMax: number;
};

// UV bounds are extracted from the supplied GLB files. The print dimensions
// remain owned by the Honeybird product spreadsheet; this table only states
// which portion of each model texture is the printable surface.
export const modelFrontUvCalibrations: Record<string, ModelUvCalibration> = {
  "10165-onesize.glb": { materialSlot: "front", uMin: 0.119913, uMax: 0.879994, vMin: 0.169767, vMax: 0.829802 },
  "10167-onesize.glb": { materialSlot: "front", uMin: 0.0171, uMax: 0.9829, vMin: 0.1863, vMax: 0.815072 },
  "10168-onesize.glb": { materialSlot: "front", uMin: 0.021383, uMax: 0.97884, vMin: 0.294479, vMax: 0.705519 },
  "10221-onesize.glb": { materialSlot: "front", uMin: 0.099414, uMax: 0.90041, vMin: 0.051166, vMax: 0.948835 },
  "10223-onesize.glb": { materialSlot: "front", uMin: 0.02109, uMax: 0.979747, vMin: -0.316861, vMax: 0.683573 },
  "10224-onesize.glb": { materialSlot: "front", uMin: -0.218351, uMax: 0.982327, vMin: -0.075487, vMax: 0.77393 },
  "10226-onesize.glb": { materialSlot: "front", uMin: 0.020446, uMax: 0.979492, vMin: 0.247469, vMax: 0.752872 },
  "10228-onesize.glb": { materialSlot: "front", uMin: 0.020061, uMax: 0.979848, vMin: 0.249659, vMax: 0.749592 },
  "10230-onesize.glb": { materialSlot: "front", uMin: 0.020673, uMax: 0.978549, vMin: 0.142872, vMax: 0.760637 },
  "10231-onesize.glb": { materialSlot: "front", uMin: 0.02055, uMax: 0.979192, vMin: 0.338541, vMax: 0.637488 },
  "10232-onesize.glb": { materialSlot: "front", uMin: 0.019678, uMax: 0.97877, vMin: 0.166361, vMax: 0.833393 },
  "10234-onesize.glb": { materialSlot: "front", uMin: 0.02013, uMax: 0.979661, vMin: 0.326167, vMax: 0.673895 },
  "10235-onesize.glb": { materialSlot: "front", uMin: 0.020008, uMax: 0.979244, vMin: 0.227849, vMax: 0.769425 },
  "10236-onesize.glb": { materialSlot: "front", uMin: 0.0246, uMax: 0.975, vMin: 0.0826, vMax: 0.915796 },
  "10241-18oz.glb": { materialSlot: "front", uMin: 0.018032, uMax: 0.981955, vMin: 0.122039, vMax: 0.877877 },
  "10241-32oz.glb": { materialSlot: "front", uMin: 0.01803, uMax: 0.981925, vMin: 0.150023, vMax: 0.849819 },
  "10241-40oz.glb": { materialSlot: "front", uMin: 0.018056, uMax: 0.981958, vMin: 0.088073, vMax: 0.911921 },
  "10242-onesize.glb": { materialSlot: "front", uMin: 0.02625, uMax: 0.973781, vMin: 0.022577, vMax: 0.979454 },
  "10244-onesize.glb": { materialSlot: "front", uMin: 0.022883, uMax: 0.976727, vMin: 0.022751, vMax: 0.97613 },
  "10245-onesize.glb": { materialSlot: "front", uMin: 0.023023, uMax: 0.9966, vMin: 0.136449, vMax: 0.862531 },
  "10246-onesize.glb": { materialSlot: "front", uMin: 0.017665, uMax: 0.982529, vMin: 0.273639, vMax: 0.727207 },
  "10247-onesize.glb": { materialSlot: "front", uMin: 0.046977, uMax: 0.95687, vMin: 0.200858, vMax: 0.796566 },
  "10248-onesize.glb": { materialSlot: "front", uMin: 0.0871, uMax: 0.9092, vMin: 0.1186, vMax: 0.893924 },
  "10249-onesize.glb": { materialSlot: "front", uMin: 0.045585, uMax: 0.956713, vMin: 0.212081, vMax: 0.789685 },
  "10252-onesize.glb": { materialSlot: "front", uMin: 0.018389, uMax: 0.981818, vMin: 0.052166, vMax: 0.947837 },
  "10256-onesize.glb": { materialSlot: "front", uMin: 0.016487, uMax: 0.983915, vMin: 0.216257, vMax: 0.781121 },
  "10344-onesize.glb": { materialSlot: "front", uMin: 0.023741, uMax: 0.97684, vMin: 0.212239, vMax: 0.787822 },
  "10345-onesize.glb": { materialSlot: "front", uMin: 0.021236, uMax: 0.980255, vMin: 0.234089, vMax: 0.764067 },
  "10350-onesize.glb": { materialSlot: "front", uMin: 0.017269, uMax: 0.983598, vMin: 0.240308, vMax: 0.758987 },
  "10351-onesize.glb": { materialSlot: "front", uMin: 0.017081, uMax: 0.982922, vMin: 0.133542, vMax: 0.863288 },
  "10376-onesize.glb": { materialSlot: "front", uMin: 0.016403, uMax: 0.983238, vMin: 0.142482, vMax: 0.857397 },
  "10385-onesize.glb": { materialSlot: "front", uMin: 0.019853, uMax: 0.980147, vMin: 0.240805, vMax: 0.759294 },
  "10395-onesize.glb": { materialSlot: "front", uMin: 0.01869, uMax: 0.982841, vMin: 0.225087, vMax: 0.777208 },
};

// Multi-surface products must not reuse the front calibration. These values
// are decoded from each GLB material's TEXCOORD_0, while print dimensions stay
// owned by the Honeybird product data.
export const modelSurfaceUvCalibrations: Record<string, Record<string, ModelUvCalibration>> = {
  "10165-onesize.glb": {
    body: { materialSlot: "front", uMin: 0.119913, uMax: 0.879994, vMin: 0.169767, vMax: 0.829802 },
    round_bottom: { materialSlot: "buttom", uMin: 0.379676, uMax: 0.620324, vMin: 0.379676, vMax: 0.620324 },
    pocket: { materialSlot: "pocket", uMin: 0.376411, uMax: 0.623033, vMin: 0.332322, vMax: 0.790126 },
    pocket_trim: { materialSlot: "pocket_edge", uMin: 0.060152, uMax: 0.939929, vMin: 0.455123, vMax: 0.541059 },
    strap: { materialSlot: "shoulderstrap", uMin: 0.284209, uMax: 0.713943, vMin: 0.433913, vMax: 0.563515 },
  },
  "10247-onesize.glb": {
    body: { materialSlot: "front", uMin: 0.046977, uMax: 0.95687, vMin: 0.200858, vMax: 0.796566 },
    bottom: { materialSlot: "buttom", uMin: 0.347563, uMax: 0.652415, vMin: 0.347574, vMax: 0.652426 },
    trim_strip: { materialSlot: "pocket_edge", uMin: 0.130149, uMax: 0.868991, vMin: 0.456269, vMax: 0.545038 },
    pocket: { materialSlot: "pocket", uMin: 0.381871, uMax: 0.620457, vMin: 0.291025, vMax: 0.726218 },
    strap: { materialSlot: "shoulder_strap", uMin: 0.262207, uMax: 0.738188, vMin: 0.425269, vMax: 0.577537 },
  },
  "10249-onesize.glb": {
    body: { materialSlot: "front", uMin: 0.045585, uMax: 0.956713, vMin: 0.212081, vMax: 0.789685 },
    base: { materialSlot: "buttom", uMin: 0.361562, uMax: 0.638437, vMin: 0.361653, vMax: 0.638461 },
  },
};

export function modelUvCalibrationForSurface(modelFile: string | null | undefined, surfaceName?: string) {
  if (!modelFile || !surfaceName || surfaceName === "handle") return null;
  const calibratedSurfaces = modelSurfaceUvCalibrations[modelFile];
  if (calibratedSurfaces) return calibratedSurfaces[surfaceName] ?? null;
  return modelFrontUvCalibrations[modelFile] ?? null;
}
