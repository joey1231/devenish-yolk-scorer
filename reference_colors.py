"""
DSM/Roche Yolk Color Fan Reference Values (L*a*b* color space).

These are the standard reference colors for the 15-point yolk color scale
used across the poultry industry. Values are approximate CIE L*a*b*
coordinates derived from published colorimetry data and spectrophotometric
measurements of the physical DSM YCF.

Score 1 = very pale yellow, Score 15 = deep orange-red.
"""

# Each entry: (L*, a*, b*)
# Sources: DSM published data, Vuilleumier (1969), Beardsworth & Hernandez (2004)
DSM_YOLK_LAB = {
    1:  (90.0,  -3.0,  30.0),
    2:  (87.0,  -1.0,  45.0),
    3:  (84.0,   2.0,  58.0),
    4:  (81.0,   6.0,  68.0),
    5:  (78.0,  10.0,  75.0),
    6:  (75.0,  15.0,  78.0),
    7:  (72.0,  20.0,  80.0),
    8:  (69.0,  26.0,  79.0),
    9:  (66.0,  32.0,  76.0),
    10: (63.0,  38.0,  72.0),
    11: (59.0,  44.0,  67.0),
    12: (55.0,  50.0,  62.0),
    13: (51.0,  55.0,  56.0),
    14: (47.0,  58.0,  50.0),
    15: (43.0,  60.0,  44.0),
}

# sRGB approximations (for visualization/debugging only -- not used in matching)
DSM_YOLK_RGB = {
    1:  (255, 230, 150),
    2:  (255, 220, 110),
    3:  (255, 210,  75),
    4:  (255, 200,  40),
    5:  (255, 190,  10),
    6:  (255, 175,   0),
    7:  (255, 160,   0),
    8:  (250, 140,   0),
    9:  (240, 120,   0),
    10: (230, 100,   0),
    11: (215,  80,   0),
    12: (200,  60,   0),
    13: (185,  45,   5),
    14: (170,  35,  10),
    15: (155,  25,  15),
}
