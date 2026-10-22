// Customer-facing subset of retained hospital results. No geometry or local machine paths.
// Numeric values come from exact report fractions; format only at presentation time.
// This is purchasing analysis, not an installed-system redesign or code approval.

export const hospital = {
  "updatedAt": "2026-10-22",
  "name": "Hospital purchasing study",
  "currency": "USD",
  "sourceCount": 7,
  "productCount": 149822,
  "coverage": {
    "sourceCount": 7,
    "productCount": 149822,
    "serviceCandidateCount": 47716,
    "segmentCount": 19352,
    "measuredCount": 18559,
    "unresolvedCount": 793,
    "measuredM": 22395.594940680745,
    "measuredPercent": 95.90223232740802,
    "pricedTradeCount": 4,
    "description": "All seven hospital design files processed. Purchasing savings cover measurable straight pipes, ducts, conduit and cable trays in four trades.",
    "notPriced": [
      "Equipment",
      "Fittings and joints",
      "Labor",
      "Insulation and supports",
      "Electrical conductors",
      "Fire alarm circuits",
      "Structure",
      "Architecture"
    ]
  },
  "baselines": [
    {
      "id": "perNetwork",
      "label": "Separate orders",
      "description": "Modeled orders placed separately for each network. This is a comparison scenario, not a contractor quote."
    },
    {
      "id": "pooled",
      "label": "Already combined",
      "description": "Orders already combined by compatible stock group using a simple packing method. Shows the smaller gain beyond combining orders."
    }
  ],
  "scenarios": {
    "broad": {
      "id": "broad",
      "label": "Broader purchasing plan",
      "description": "Includes measurable straight material with assumed fabrication joints.",
      "plannedCount": 18559,
      "excludedCount": 0,
      "fabricationPieceCount": 22016,
      "groupCount": 472,
      "additionalJoints": 3457,
      "seconds": 231.625,
      "plans": {
        "perNetwork": {
          "costUsd": 556773.5828638703,
          "purchasedM": 24994.8192,
          "requiredM": 22405.031,
          "wasteM": 2589.7882,
          "stockCount": 10052,
          "pieceCount": 22016,
          "kerfM": 54.252,
          "trimM": 50.26,
          "offcutM": 2485.2762,
          "exact": {
            "costUsd": "1684569012314922632058790667277131/3025590768243750000000000000",
            "purchasedM": "15621762/625",
            "requiredM": "22405031/1000",
            "wasteM": "12948941/5000"
          }
        },
        "pooled": {
          "costUsd": 522002.0654064111,
          "purchasedM": 23340.6696,
          "requiredM": 22405.031,
          "wasteM": 935.6386,
          "stockCount": 9371,
          "pieceCount": 22016,
          "kerfM": 54.252,
          "trimM": 46.855,
          "offcutM": 834.5316,
          "exact": {
            "costUsd": "123871735693945681711791295074517/237301236725000000000000000",
            "purchasedM": "29175837/1250",
            "requiredM": "22405031/1000",
            "wasteM": "4678193/5000"
          }
        },
        "selected": {
          "costUsd": 521709.64858344814,
          "purchasedM": 23326.0392,
          "requiredM": 22405.031,
          "wasteM": 921.0082,
          "stockCount": 9365,
          "pieceCount": 22016,
          "kerfM": 54.252,
          "trimM": 46.825,
          "offcutM": 819.9312,
          "exact": {
            "costUsd": "371407034460652157176798973467259/711903710175000000000000000",
            "purchasedM": "29157549/1250",
            "requiredM": "22405031/1000",
            "wasteM": "4605041/5000"
          }
        }
      },
      "sources": [
        {
          "id": "architecture",
          "label": "Architecture",
          "fileName": "arc_ifc4.ifc",
          "sourceHash": "230afa4d72a59c9ce18cdd9a7bc7c5c3e409a46078de6e14b19741b4cf92cf09",
          "productCount": 15316,
          "segmentCount": 0,
          "measuredCount": 0,
          "unresolvedCount": 0,
          "measuredM": 0.0,
          "plannedCount": 0,
          "excludedCount": 0,
          "additionalJoints": 0,
          "scope": "Counted; no purchasing saving calculated",
          "plans": {
            "perNetwork": {
              "costUsd": 0.0,
              "purchasedM": 0.0,
              "requiredM": 0.0,
              "wasteM": 0.0,
              "stockCount": 0,
              "pieceCount": 0,
              "kerfM": 0.0,
              "trimM": 0.0,
              "offcutM": 0.0,
              "exact": {
                "costUsd": "0",
                "purchasedM": "0",
                "requiredM": "0",
                "wasteM": "0"
              }
            },
            "pooled": {
              "costUsd": 0.0,
              "purchasedM": 0.0,
              "requiredM": 0.0,
              "wasteM": 0.0,
              "stockCount": 0,
              "pieceCount": 0,
              "kerfM": 0.0,
              "trimM": 0.0,
              "offcutM": 0.0,
              "exact": {
                "costUsd": "0",
                "purchasedM": "0",
                "requiredM": "0",
                "wasteM": "0"
              }
            },
            "selected": {
              "costUsd": 0.0,
              "purchasedM": 0.0,
              "requiredM": 0.0,
              "wasteM": 0.0,
              "stockCount": 0,
              "pieceCount": 0,
              "kerfM": 0.0,
              "trimM": 0.0,
              "offcutM": 0.0,
              "exact": {
                "costUsd": "0",
                "purchasedM": "0",
                "requiredM": "0",
                "wasteM": "0"
              }
            }
          }
        },
        {
          "id": "electrical",
          "label": "Electrical containment",
          "fileName": "elec_ifc4.ifc",
          "sourceHash": "8e404c4e4c9085338383a89ae57a3a31ebe96ee406214392a1bf69a6775dcecc",
          "productCount": 6305,
          "segmentCount": 84,
          "measuredCount": 80,
          "unresolvedCount": 4,
          "measuredM": 417.5140382615411,
          "plannedCount": 80,
          "excludedCount": 0,
          "additionalJoints": 106,
          "scope": "Straight pipes, ducts and electrical containment",
          "plans": {
            "perNetwork": {
              "costUsd": 16833.02090610325,
              "purchasedM": 457.2,
              "requiredM": 417.559,
              "wasteM": 39.641,
              "stockCount": 150,
              "pieceCount": 186,
              "kerfM": 0.558,
              "trimM": 0.75,
              "offcutM": 38.333,
              "exact": {
                "costUsd": "47305097999502098333/2810256000000000",
                "purchasedM": "2286/5",
                "requiredM": "417559/1000",
                "wasteM": "39641/1000"
              }
            },
            "pooled": {
              "costUsd": 16749.030693111978,
              "purchasedM": 448.056,
              "requiredM": 417.559,
              "wasteM": 30.497,
              "stockCount": 147,
              "pieceCount": 186,
              "kerfM": 0.558,
              "trimM": 0.735,
              "offcutM": 29.204,
              "exact": {
                "costUsd": "47069063999502098333/2810256000000000",
                "purchasedM": "56007/125",
                "requiredM": "417559/1000",
                "wasteM": "30497/1000"
              }
            },
            "selected": {
              "costUsd": 16749.030693111978,
              "purchasedM": 448.056,
              "requiredM": 417.559,
              "wasteM": 30.497,
              "stockCount": 147,
              "pieceCount": 186,
              "kerfM": 0.558,
              "trimM": 0.735,
              "offcutM": 29.204,
              "exact": {
                "costUsd": "47069063999502098333/2810256000000000",
                "purchasedM": "56007/125",
                "requiredM": "417559/1000",
                "wasteM": "30497/1000"
              }
            }
          }
        },
        {
          "id": "fire",
          "label": "Fire alarm",
          "fileName": "fire_ifc4.ifc",
          "sourceHash": "f04e6fb62ad10cd78177d1d390758e912e3ad65881a184cca8ea1da07c59ae23",
          "productCount": 874,
          "segmentCount": 0,
          "measuredCount": 0,
          "unresolvedCount": 0,
          "measuredM": 0.0,
          "plannedCount": 0,
          "excludedCount": 0,
          "additionalJoints": 0,
          "scope": "Counted; no purchasing saving calculated",
          "plans": {
            "perNetwork": {
              "costUsd": 0.0,
              "purchasedM": 0.0,
              "requiredM": 0.0,
              "wasteM": 0.0,
              "stockCount": 0,
              "pieceCount": 0,
              "kerfM": 0.0,
              "trimM": 0.0,
              "offcutM": 0.0,
              "exact": {
                "costUsd": "0",
                "purchasedM": "0",
                "requiredM": "0",
                "wasteM": "0"
              }
            },
            "pooled": {
              "costUsd": 0.0,
              "purchasedM": 0.0,
              "requiredM": 0.0,
              "wasteM": 0.0,
              "stockCount": 0,
              "pieceCount": 0,
              "kerfM": 0.0,
              "trimM": 0.0,
              "offcutM": 0.0,
              "exact": {
                "costUsd": "0",
                "purchasedM": "0",
                "requiredM": "0",
                "wasteM": "0"
              }
            },
            "selected": {
              "costUsd": 0.0,
              "purchasedM": 0.0,
              "requiredM": 0.0,
              "wasteM": 0.0,
              "stockCount": 0,
              "pieceCount": 0,
              "kerfM": 0.0,
              "trimM": 0.0,
              "offcutM": 0.0,
              "exact": {
                "costUsd": "0",
                "purchasedM": "0",
                "requiredM": "0",
                "wasteM": "0"
              }
            }
          }
        },
        {
          "id": "hvac",
          "label": "Heating & cooling",
          "fileName": "mech_ifc4.ifc",
          "sourceHash": "04a29bc312fe0b026634ad86390e8b72c1d1c1765255351f787503d3d8ce1c13",
          "productCount": 59215,
          "segmentCount": 8732,
          "measuredCount": 7944,
          "unresolvedCount": 788,
          "measuredM": 10739.702914960946,
          "plannedCount": 7944,
          "excludedCount": 0,
          "additionalJoints": 2591,
          "scope": "Straight pipes, ducts and electrical containment",
          "plans": {
            "perNetwork": {
              "costUsd": 376687.9942898687,
              "purchasedM": 12360.2496,
              "requiredM": 10743.67,
              "wasteM": 1616.5796,
              "stockCount": 6074,
              "pieceCount": 10535,
              "kerfM": 19.809,
              "trimM": 30.37,
              "offcutM": 1566.4006,
              "exact": {
                "costUsd": "1908791073465051464161223/5067300000000000000",
                "purchasedM": "7725156/625",
                "requiredM": "1074367/100",
                "wasteM": "4041449/2500"
              }
            },
            "pooled": {
              "costUsd": 352816.8677531232,
              "purchasedM": 11451.336,
              "requiredM": 10743.67,
              "wasteM": 707.666,
              "stockCount": 5610,
              "pieceCount": 10535,
              "kerfM": 19.809,
              "trimM": 28.05,
              "offcutM": 659.807,
              "exact": {
                "costUsd": "595942971321800472051979/1689100000000000000",
                "purchasedM": "1431417/125",
                "requiredM": "1074367/100",
                "wasteM": "353833/500"
              }
            },
            "selected": {
              "costUsd": 352598.70333617536,
              "purchasedM": 11445.8496,
              "requiredM": 10743.67,
              "wasteM": 702.1796,
              "stockCount": 5607,
              "pieceCount": 10535,
              "kerfM": 19.809,
              "trimM": 28.035,
              "offcutM": 654.3356,
              "exact": {
                "costUsd": "89336170470770070891527/253365000000000000",
                "purchasedM": "7153656/625",
                "requiredM": "1074367/100",
                "wasteM": "1755449/2500"
              }
            }
          }
        },
        {
          "id": "plumbing",
          "label": "Plumbing",
          "fileName": "plumb_ifc4.ifc",
          "sourceHash": "bb53f0eb8f7295e91e0fb6ec6b79a30022a2e0e248714aab6bb1a8930c4793dd",
          "productCount": 26942,
          "segmentCount": 4308,
          "measuredCount": 4308,
          "unresolvedCount": 0,
          "measuredM": 3899.0940401076523,
          "plannedCount": 4308,
          "excludedCount": 0,
          "additionalJoints": 286,
          "scope": "Straight pipes, ducts and electrical containment",
          "plans": {
            "perNetwork": {
              "costUsd": 39007.57110535471,
              "purchasedM": 4215.384,
              "requiredM": 3901.415,
              "wasteM": 313.969,
              "stockCount": 1383,
              "pieceCount": 4594,
              "kerfM": 13.782,
              "trimM": 6.915,
              "offcutM": 293.272,
              "exact": {
                "costUsd": "32253320451049/826847700",
                "purchasedM": "526923/125",
                "requiredM": "780283/200",
                "wasteM": "313969/1000"
              }
            },
            "pooled": {
              "costUsd": 36557.842608952655,
              "purchasedM": 3971.544,
              "requiredM": 3901.415,
              "wasteM": 70.129,
              "stockCount": 1303,
              "pieceCount": 4594,
              "kerfM": 13.782,
              "trimM": 6.515,
              "offcutM": 49.832,
              "exact": {
                "costUsd": "3556208009197/97276200",
                "purchasedM": "496443/125",
                "requiredM": "780283/200",
                "wasteM": "70129/1000"
              }
            },
            "selected": {
              "costUsd": 36547.66403752408,
              "purchasedM": 3968.496,
              "requiredM": 3901.415,
              "wasteM": 67.081,
              "stockCount": 1302,
              "pieceCount": 4594,
              "kerfM": 13.782,
              "trimM": 6.51,
              "offcutM": 46.789,
              "exact": {
                "costUsd": "3555217876447/97276200",
                "purchasedM": "496062/125",
                "requiredM": "780283/200",
                "wasteM": "67081/1000"
              }
            }
          }
        },
        {
          "id": "sprinkler",
          "label": "Sprinklers",
          "fileName": "sprinkle_ifc4.ifc",
          "sourceHash": "0e30c25a77ebcd75b2fc3a6cb87dc3891bd476f60a269e36eb5e0149bcc06ea7",
          "productCount": 38255,
          "segmentCount": 6228,
          "measuredCount": 6227,
          "unresolvedCount": 1,
          "measuredM": 7339.2839473506065,
          "plannedCount": 6227,
          "excludedCount": 0,
          "additionalJoints": 474,
          "scope": "Straight pipes, ducts and electrical containment",
          "plans": {
            "perNetwork": {
              "costUsd": 124244.9965625437,
              "purchasedM": 7961.9856,
              "requiredM": 7342.387,
              "wasteM": 619.5986,
              "stockCount": 2445,
              "pieceCount": 6701,
              "kerfM": 20.103,
              "trimM": 12.225,
              "offcutM": 587.2706,
              "exact": {
                "costUsd": "251793356971194046262258171/2026587500000000000000",
                "purchasedM": "4976241/625",
                "requiredM": "7342387/1000",
                "wasteM": "3097993/5000"
              }
            },
            "pooled": {
              "costUsd": 115878.32435122317,
              "purchasedM": 7469.7336,
              "requiredM": 7342.387,
              "wasteM": 127.3466,
              "stockCount": 2311,
              "pieceCount": 6701,
              "kerfM": 20.103,
              "trimM": 11.555,
              "offcutM": 95.6886,
              "exact": {
                "costUsd": "469675127302268985127628261/4053175000000000000000",
                "purchasedM": "9337167/1250",
                "requiredM": "7342387/1000",
                "wasteM": "636733/5000"
              }
            },
            "selected": {
              "costUsd": 115814.2505166367,
              "purchasedM": 7463.6376,
              "requiredM": 7342.387,
              "wasteM": 121.2506,
              "stockCount": 2309,
              "pieceCount": 6701,
              "kerfM": 20.103,
              "trimM": 11.545,
              "offcutM": 89.6026,
              "exact": {
                "costUsd": "469415424837768985447374399/4053175000000000000000",
                "purchasedM": "9329547/1250",
                "requiredM": "7342387/1000",
                "wasteM": "606253/5000"
              }
            }
          }
        },
        {
          "id": "structure",
          "label": "Structure",
          "fileName": "str_ifc4.ifc",
          "sourceHash": "7eed88eb21dafdc5a5950d9b1ee18df3fd00fcd376a14fd1bae80658e371975e",
          "productCount": 2915,
          "segmentCount": 0,
          "measuredCount": 0,
          "unresolvedCount": 0,
          "measuredM": 0.0,
          "plannedCount": 0,
          "excludedCount": 0,
          "additionalJoints": 0,
          "scope": "Counted; no purchasing saving calculated",
          "plans": {
            "perNetwork": {
              "costUsd": 0.0,
              "purchasedM": 0.0,
              "requiredM": 0.0,
              "wasteM": 0.0,
              "stockCount": 0,
              "pieceCount": 0,
              "kerfM": 0.0,
              "trimM": 0.0,
              "offcutM": 0.0,
              "exact": {
                "costUsd": "0",
                "purchasedM": "0",
                "requiredM": "0",
                "wasteM": "0"
              }
            },
            "pooled": {
              "costUsd": 0.0,
              "purchasedM": 0.0,
              "requiredM": 0.0,
              "wasteM": 0.0,
              "stockCount": 0,
              "pieceCount": 0,
              "kerfM": 0.0,
              "trimM": 0.0,
              "offcutM": 0.0,
              "exact": {
                "costUsd": "0",
                "purchasedM": "0",
                "requiredM": "0",
                "wasteM": "0"
              }
            },
            "selected": {
              "costUsd": 0.0,
              "purchasedM": 0.0,
              "requiredM": 0.0,
              "wasteM": 0.0,
              "stockCount": 0,
              "pieceCount": 0,
              "kerfM": 0.0,
              "trimM": 0.0,
              "offcutM": 0.0,
              "exact": {
                "costUsd": "0",
                "purchasedM": "0",
                "requiredM": "0",
                "wasteM": "0"
              }
            }
          }
        }
      ],
      "trades": [
        {
          "id": "electrical",
          "label": "Electrical containment",
          "fileName": "elec_ifc4.ifc",
          "sourceHash": "8e404c4e4c9085338383a89ae57a3a31ebe96ee406214392a1bf69a6775dcecc",
          "productCount": 6305,
          "segmentCount": 84,
          "measuredCount": 80,
          "unresolvedCount": 4,
          "measuredM": 417.5140382615411,
          "plannedCount": 80,
          "excludedCount": 0,
          "additionalJoints": 106,
          "scope": "Straight pipes, ducts and electrical containment",
          "plans": {
            "perNetwork": {
              "costUsd": 16833.02090610325,
              "purchasedM": 457.2,
              "requiredM": 417.559,
              "wasteM": 39.641,
              "stockCount": 150,
              "pieceCount": 186,
              "kerfM": 0.558,
              "trimM": 0.75,
              "offcutM": 38.333,
              "exact": {
                "costUsd": "47305097999502098333/2810256000000000",
                "purchasedM": "2286/5",
                "requiredM": "417559/1000",
                "wasteM": "39641/1000"
              }
            },
            "pooled": {
              "costUsd": 16749.030693111978,
              "purchasedM": 448.056,
              "requiredM": 417.559,
              "wasteM": 30.497,
              "stockCount": 147,
              "pieceCount": 186,
              "kerfM": 0.558,
              "trimM": 0.735,
              "offcutM": 29.204,
              "exact": {
                "costUsd": "47069063999502098333/2810256000000000",
                "purchasedM": "56007/125",
                "requiredM": "417559/1000",
                "wasteM": "30497/1000"
              }
            },
            "selected": {
              "costUsd": 16749.030693111978,
              "purchasedM": 448.056,
              "requiredM": 417.559,
              "wasteM": 30.497,
              "stockCount": 147,
              "pieceCount": 186,
              "kerfM": 0.558,
              "trimM": 0.735,
              "offcutM": 29.204,
              "exact": {
                "costUsd": "47069063999502098333/2810256000000000",
                "purchasedM": "56007/125",
                "requiredM": "417559/1000",
                "wasteM": "30497/1000"
              }
            }
          }
        },
        {
          "id": "hvac",
          "label": "Heating & cooling",
          "fileName": "mech_ifc4.ifc",
          "sourceHash": "04a29bc312fe0b026634ad86390e8b72c1d1c1765255351f787503d3d8ce1c13",
          "productCount": 59215,
          "segmentCount": 8732,
          "measuredCount": 7944,
          "unresolvedCount": 788,
          "measuredM": 10739.702914960946,
          "plannedCount": 7944,
          "excludedCount": 0,
          "additionalJoints": 2591,
          "scope": "Straight pipes, ducts and electrical containment",
          "plans": {
            "perNetwork": {
              "costUsd": 376687.9942898687,
              "purchasedM": 12360.2496,
              "requiredM": 10743.67,
              "wasteM": 1616.5796,
              "stockCount": 6074,
              "pieceCount": 10535,
              "kerfM": 19.809,
              "trimM": 30.37,
              "offcutM": 1566.4006,
              "exact": {
                "costUsd": "1908791073465051464161223/5067300000000000000",
                "purchasedM": "7725156/625",
                "requiredM": "1074367/100",
                "wasteM": "4041449/2500"
              }
            },
            "pooled": {
              "costUsd": 352816.8677531232,
              "purchasedM": 11451.336,
              "requiredM": 10743.67,
              "wasteM": 707.666,
              "stockCount": 5610,
              "pieceCount": 10535,
              "kerfM": 19.809,
              "trimM": 28.05,
              "offcutM": 659.807,
              "exact": {
                "costUsd": "595942971321800472051979/1689100000000000000",
                "purchasedM": "1431417/125",
                "requiredM": "1074367/100",
                "wasteM": "353833/500"
              }
            },
            "selected": {
              "costUsd": 352598.70333617536,
              "purchasedM": 11445.8496,
              "requiredM": 10743.67,
              "wasteM": 702.1796,
              "stockCount": 5607,
              "pieceCount": 10535,
              "kerfM": 19.809,
              "trimM": 28.035,
              "offcutM": 654.3356,
              "exact": {
                "costUsd": "89336170470770070891527/253365000000000000",
                "purchasedM": "7153656/625",
                "requiredM": "1074367/100",
                "wasteM": "1755449/2500"
              }
            }
          }
        },
        {
          "id": "plumbing",
          "label": "Plumbing",
          "fileName": "plumb_ifc4.ifc",
          "sourceHash": "bb53f0eb8f7295e91e0fb6ec6b79a30022a2e0e248714aab6bb1a8930c4793dd",
          "productCount": 26942,
          "segmentCount": 4308,
          "measuredCount": 4308,
          "unresolvedCount": 0,
          "measuredM": 3899.0940401076523,
          "plannedCount": 4308,
          "excludedCount": 0,
          "additionalJoints": 286,
          "scope": "Straight pipes, ducts and electrical containment",
          "plans": {
            "perNetwork": {
              "costUsd": 39007.57110535471,
              "purchasedM": 4215.384,
              "requiredM": 3901.415,
              "wasteM": 313.969,
              "stockCount": 1383,
              "pieceCount": 4594,
              "kerfM": 13.782,
              "trimM": 6.915,
              "offcutM": 293.272,
              "exact": {
                "costUsd": "32253320451049/826847700",
                "purchasedM": "526923/125",
                "requiredM": "780283/200",
                "wasteM": "313969/1000"
              }
            },
            "pooled": {
              "costUsd": 36557.842608952655,
              "purchasedM": 3971.544,
              "requiredM": 3901.415,
              "wasteM": 70.129,
              "stockCount": 1303,
              "pieceCount": 4594,
              "kerfM": 13.782,
              "trimM": 6.515,
              "offcutM": 49.832,
              "exact": {
                "costUsd": "3556208009197/97276200",
                "purchasedM": "496443/125",
                "requiredM": "780283/200",
                "wasteM": "70129/1000"
              }
            },
            "selected": {
              "costUsd": 36547.66403752408,
              "purchasedM": 3968.496,
              "requiredM": 3901.415,
              "wasteM": 67.081,
              "stockCount": 1302,
              "pieceCount": 4594,
              "kerfM": 13.782,
              "trimM": 6.51,
              "offcutM": 46.789,
              "exact": {
                "costUsd": "3555217876447/97276200",
                "purchasedM": "496062/125",
                "requiredM": "780283/200",
                "wasteM": "67081/1000"
              }
            }
          }
        },
        {
          "id": "sprinkler",
          "label": "Sprinklers",
          "fileName": "sprinkle_ifc4.ifc",
          "sourceHash": "0e30c25a77ebcd75b2fc3a6cb87dc3891bd476f60a269e36eb5e0149bcc06ea7",
          "productCount": 38255,
          "segmentCount": 6228,
          "measuredCount": 6227,
          "unresolvedCount": 1,
          "measuredM": 7339.2839473506065,
          "plannedCount": 6227,
          "excludedCount": 0,
          "additionalJoints": 474,
          "scope": "Straight pipes, ducts and electrical containment",
          "plans": {
            "perNetwork": {
              "costUsd": 124244.9965625437,
              "purchasedM": 7961.9856,
              "requiredM": 7342.387,
              "wasteM": 619.5986,
              "stockCount": 2445,
              "pieceCount": 6701,
              "kerfM": 20.103,
              "trimM": 12.225,
              "offcutM": 587.2706,
              "exact": {
                "costUsd": "251793356971194046262258171/2026587500000000000000",
                "purchasedM": "4976241/625",
                "requiredM": "7342387/1000",
                "wasteM": "3097993/5000"
              }
            },
            "pooled": {
              "costUsd": 115878.32435122317,
              "purchasedM": 7469.7336,
              "requiredM": 7342.387,
              "wasteM": 127.3466,
              "stockCount": 2311,
              "pieceCount": 6701,
              "kerfM": 20.103,
              "trimM": 11.555,
              "offcutM": 95.6886,
              "exact": {
                "costUsd": "469675127302268985127628261/4053175000000000000000",
                "purchasedM": "9337167/1250",
                "requiredM": "7342387/1000",
                "wasteM": "636733/5000"
              }
            },
            "selected": {
              "costUsd": 115814.2505166367,
              "purchasedM": 7463.6376,
              "requiredM": 7342.387,
              "wasteM": 121.2506,
              "stockCount": 2309,
              "pieceCount": 6701,
              "kerfM": 20.103,
              "trimM": 11.545,
              "offcutM": 89.6026,
              "exact": {
                "costUsd": "469415424837768985447374399/4053175000000000000000",
                "purchasedM": "9329547/1250",
                "requiredM": "7342387/1000",
                "wasteM": "606253/5000"
              }
            }
          }
        }
      ],
      "provenance": {
        "campaignId": "2f25fd1064cb4547ae3667b9bbd4e69b",
        "runId": "d78c7888d76c4957aa49146b9536e9cb",
        "reportPath": "evidence/benchmarks/hospital-whole-procurement/2f25fd1064cb4547ae3667b9bbd4e69b/campaign/report.json",
        "reportSha256": "7677d030e92b31b6149092050e2ff4dc8ddac1d603a876bef12a187f18635780",
        "planRoot": "710c4dd3ce91a237aa523aa20af34f8eaec8626a8a2c4c40c9cb9aeb5154390c",
        "requestRoot": "f6d4a9fa245bd8b816be0caa01fa3bbad478c66e4cf94f705515bc4f5133d642",
        "baseRoot": "221aa7fdb8ebc8f82122addb2c1d6204aae75166b24933ed6d5178740afee27d",
        "packetRoot": "0cf967e84c6da3385aa6683ee2c664a6e0cd1c8f8e3843f63f82e15a3182df17"
      }
    },
    "noSplice": {
      "id": "noSplice",
      "label": "No added joints",
      "description": "Keeps measured spans whole; overlength spans remain unplanned.",
      "plannedCount": 16446,
      "excludedCount": 2113,
      "fabricationPieceCount": 16446,
      "groupCount": 383,
      "additionalJoints": 0,
      "seconds": 224.859,
      "plans": {
        "perNetwork": {
          "costUsd": 232197.39603571442,
          "purchasedM": 14655.0888,
          "requiredM": 12496.777,
          "wasteM": 2158.3118,
          "stockCount": 5410,
          "pieceCount": 16446,
          "kerfM": 43.044,
          "trimM": 27.05,
          "offcutM": 2088.2178,
          "exact": {
            "costUsd": "5620274382847163935869861348573517/24204726145950000000000000000",
            "purchasedM": "18318861/1250",
            "requiredM": "12496777/1000",
            "wasteM": "10791559/5000"
          }
        },
        "pooled": {
          "costUsd": 203553.04849770473,
          "purchasedM": 13164.6168,
          "requiredM": 12496.777,
          "wasteM": 667.8398,
          "stockCount": 4839,
          "pieceCount": 16446,
          "kerfM": 43.044,
          "trimM": 24.195,
          "offcutM": 600.6008,
          "exact": {
            "costUsd": "4926945795060222179026136340286271/24204726145950000000000000000",
            "purchasedM": "16455771/1250",
            "requiredM": "12496777/1000",
            "wasteM": "3339199/5000"
          }
        },
        "selected": {
          "costUsd": 202791.99505149078,
          "purchasedM": 13148.1576,
          "requiredM": 12496.777,
          "wasteM": 651.3806,
          "stockCount": 4833,
          "pieceCount": 16446,
          "kerfM": 43.044,
          "trimM": 24.165,
          "offcutM": 584.1716,
          "exact": {
            "costUsd": "4908524704812181795419322526517671/24204726145950000000000000000",
            "purchasedM": "16435197/1250",
            "requiredM": "12496777/1000",
            "wasteM": "3256903/5000"
          }
        }
      },
      "sources": [
        {
          "id": "architecture",
          "label": "Architecture",
          "fileName": "arc_ifc4.ifc",
          "sourceHash": "230afa4d72a59c9ce18cdd9a7bc7c5c3e409a46078de6e14b19741b4cf92cf09",
          "productCount": 15316,
          "segmentCount": 0,
          "measuredCount": 0,
          "unresolvedCount": 0,
          "measuredM": 0.0,
          "plannedCount": 0,
          "excludedCount": 0,
          "additionalJoints": 0,
          "scope": "Counted; no purchasing saving calculated",
          "plans": {
            "perNetwork": {
              "costUsd": 0.0,
              "purchasedM": 0.0,
              "requiredM": 0.0,
              "wasteM": 0.0,
              "stockCount": 0,
              "pieceCount": 0,
              "kerfM": 0.0,
              "trimM": 0.0,
              "offcutM": 0.0,
              "exact": {
                "costUsd": "0",
                "purchasedM": "0",
                "requiredM": "0",
                "wasteM": "0"
              }
            },
            "pooled": {
              "costUsd": 0.0,
              "purchasedM": 0.0,
              "requiredM": 0.0,
              "wasteM": 0.0,
              "stockCount": 0,
              "pieceCount": 0,
              "kerfM": 0.0,
              "trimM": 0.0,
              "offcutM": 0.0,
              "exact": {
                "costUsd": "0",
                "purchasedM": "0",
                "requiredM": "0",
                "wasteM": "0"
              }
            },
            "selected": {
              "costUsd": 0.0,
              "purchasedM": 0.0,
              "requiredM": 0.0,
              "wasteM": 0.0,
              "stockCount": 0,
              "pieceCount": 0,
              "kerfM": 0.0,
              "trimM": 0.0,
              "offcutM": 0.0,
              "exact": {
                "costUsd": "0",
                "purchasedM": "0",
                "requiredM": "0",
                "wasteM": "0"
              }
            }
          }
        },
        {
          "id": "electrical",
          "label": "Electrical containment",
          "fileName": "elec_ifc4.ifc",
          "sourceHash": "8e404c4e4c9085338383a89ae57a3a31ebe96ee406214392a1bf69a6775dcecc",
          "productCount": 6305,
          "segmentCount": 84,
          "measuredCount": 80,
          "unresolvedCount": 4,
          "measuredM": 417.5140382615411,
          "plannedCount": 53,
          "excludedCount": 27,
          "additionalJoints": 0,
          "scope": "Straight pipes, ducts and electrical containment",
          "plans": {
            "perNetwork": {
              "costUsd": 3011.8958911579502,
              "purchasedM": 82.296,
              "requiredM": 50.736,
              "wasteM": 31.56,
              "stockCount": 27,
              "pieceCount": 53,
              "kerfM": 0.159,
              "trimM": 0.135,
              "offcutM": 31.266,
              "exact": {
                "costUsd": "22571195998671936909/7494016000000000",
                "purchasedM": "10287/125",
                "requiredM": "6342/125",
                "wasteM": "789/25"
              }
            },
            "pooled": {
              "costUsd": 2955.9024158304355,
              "purchasedM": 76.2,
              "requiredM": 50.736,
              "wasteM": 25.464,
              "stockCount": 25,
              "pieceCount": 53,
              "kerfM": 0.159,
              "trimM": 0.125,
              "offcutM": 25.18,
              "exact": {
                "costUsd": "22151579998671936909/7494016000000000",
                "purchasedM": "381/5",
                "requiredM": "6342/125",
                "wasteM": "3183/125"
              }
            },
            "selected": {
              "costUsd": 2955.9024158304355,
              "purchasedM": 76.2,
              "requiredM": 50.736,
              "wasteM": 25.464,
              "stockCount": 25,
              "pieceCount": 53,
              "kerfM": 0.159,
              "trimM": 0.125,
              "offcutM": 25.18,
              "exact": {
                "costUsd": "22151579998671936909/7494016000000000",
                "purchasedM": "381/5",
                "requiredM": "6342/125",
                "wasteM": "3183/125"
              }
            }
          }
        },
        {
          "id": "fire",
          "label": "Fire alarm",
          "fileName": "fire_ifc4.ifc",
          "sourceHash": "f04e6fb62ad10cd78177d1d390758e912e3ad65881a184cca8ea1da07c59ae23",
          "productCount": 874,
          "segmentCount": 0,
          "measuredCount": 0,
          "unresolvedCount": 0,
          "measuredM": 0.0,
          "plannedCount": 0,
          "excludedCount": 0,
          "additionalJoints": 0,
          "scope": "Counted; no purchasing saving calculated",
          "plans": {
            "perNetwork": {
              "costUsd": 0.0,
              "purchasedM": 0.0,
              "requiredM": 0.0,
              "wasteM": 0.0,
              "stockCount": 0,
              "pieceCount": 0,
              "kerfM": 0.0,
              "trimM": 0.0,
              "offcutM": 0.0,
              "exact": {
                "costUsd": "0",
                "purchasedM": "0",
                "requiredM": "0",
                "wasteM": "0"
              }
            },
            "pooled": {
              "costUsd": 0.0,
              "purchasedM": 0.0,
              "requiredM": 0.0,
              "wasteM": 0.0,
              "stockCount": 0,
              "pieceCount": 0,
              "kerfM": 0.0,
              "trimM": 0.0,
              "offcutM": 0.0,
              "exact": {
                "costUsd": "0",
                "purchasedM": "0",
                "requiredM": "0",
                "wasteM": "0"
              }
            },
            "selected": {
              "costUsd": 0.0,
              "purchasedM": 0.0,
              "requiredM": 0.0,
              "wasteM": 0.0,
              "stockCount": 0,
              "pieceCount": 0,
              "kerfM": 0.0,
              "trimM": 0.0,
              "offcutM": 0.0,
              "exact": {
                "costUsd": "0",
                "purchasedM": "0",
                "requiredM": "0",
                "wasteM": "0"
              }
            }
          }
        },
        {
          "id": "hvac",
          "label": "Heating & cooling",
          "fileName": "mech_ifc4.ifc",
          "sourceHash": "04a29bc312fe0b026634ad86390e8b72c1d1c1765255351f787503d3d8ce1c13",
          "productCount": 59215,
          "segmentCount": 8732,
          "measuredCount": 7944,
          "unresolvedCount": 788,
          "measuredM": 10739.702914960946,
          "plannedCount": 6480,
          "excludedCount": 1464,
          "additionalJoints": 0,
          "scope": "Straight pipes, ducts and electrical containment",
          "plans": {
            "perNetwork": {
              "costUsd": 124301.1874393761,
              "purchasedM": 5605.5768,
              "requiredM": 4365.456,
              "wasteM": 1240.1208,
              "stockCount": 2584,
              "pieceCount": 6480,
              "kerfM": 13.146,
              "trimM": 12.92,
              "offcutM": 1214.0548,
              "exact": {
                "costUsd": "52489283925962538888003/422275000000000000",
                "purchasedM": "7006971/1250",
                "requiredM": "545682/125",
                "wasteM": "1550151/1250"
              }
            },
            "pooled": {
              "costUsd": 106169.76596431047,
              "purchasedM": 4829.8608,
              "requiredM": 4365.456,
              "wasteM": 464.4048,
              "stockCount": 2220,
              "pieceCount": 6480,
              "kerfM": 13.146,
              "trimM": 11.1,
              "offcutM": 440.1588,
              "exact": {
                "costUsd": "537994055070950431489373/5067300000000000000",
                "purchasedM": "3018663/625",
                "requiredM": "545682/125",
                "wasteM": "290253/625"
              }
            },
            "selected": {
              "costUsd": 105429.06966095365,
              "purchasedM": 4819.4976,
              "requiredM": 4365.456,
              "wasteM": 454.0416,
              "stockCount": 2216,
              "pieceCount": 6480,
              "kerfM": 13.146,
              "trimM": 11.08,
              "offcutM": 429.8156,
              "exact": {
                "costUsd": "66780090586618804145497/633412500000000000",
                "purchasedM": "3012186/625",
                "requiredM": "545682/125",
                "wasteM": "283776/625"
              }
            }
          }
        },
        {
          "id": "plumbing",
          "label": "Plumbing",
          "fileName": "plumb_ifc4.ifc",
          "sourceHash": "bb53f0eb8f7295e91e0fb6ec6b79a30022a2e0e248714aab6bb1a8930c4793dd",
          "productCount": 26942,
          "segmentCount": 4308,
          "measuredCount": 4308,
          "unresolvedCount": 0,
          "measuredM": 3899.0940401076523,
          "plannedCount": 4084,
          "excludedCount": 224,
          "additionalJoints": 0,
          "scope": "Straight pipes, ducts and electrical containment",
          "plans": {
            "perNetwork": {
              "costUsd": 19686.481105042683,
              "purchasedM": 2904.744,
              "requiredM": 2631.394,
              "wasteM": 273.35,
              "stockCount": 953,
              "pieceCount": 4084,
              "kerfM": 12.252,
              "trimM": 4.765,
              "offcutM": 256.333,
              "exact": {
                "costUsd": "8138860811399/413423850",
                "purchasedM": "363093/125",
                "requiredM": "1315697/500",
                "wasteM": "5467/20"
              }
            },
            "pooled": {
              "costUsd": 17580.720828997288,
              "purchasedM": 2685.288,
              "requiredM": 2631.394,
              "wasteM": 53.894,
              "stockCount": 881,
              "pieceCount": 4084,
              "kerfM": 12.252,
              "trimM": 4.405,
              "offcutM": 37.237,
              "exact": {
                "costUsd": "29073157163597/1653695400",
                "purchasedM": "335661/125",
                "requiredM": "1315697/500",
                "wasteM": "26947/500"
              }
            },
            "selected": {
              "costUsd": 17570.542257568715,
              "purchasedM": 2682.24,
              "requiredM": 2631.394,
              "wasteM": 50.846,
              "stockCount": 880,
              "pieceCount": 4084,
              "kerfM": 12.252,
              "trimM": 4.4,
              "offcutM": 34.194,
              "exact": {
                "costUsd": "4150903558121/236242200",
                "purchasedM": "67056/25",
                "requiredM": "1315697/500",
                "wasteM": "25423/500"
              }
            }
          }
        },
        {
          "id": "sprinkler",
          "label": "Sprinklers",
          "fileName": "sprinkle_ifc4.ifc",
          "sourceHash": "0e30c25a77ebcd75b2fc3a6cb87dc3891bd476f60a269e36eb5e0149bcc06ea7",
          "productCount": 38255,
          "segmentCount": 6228,
          "measuredCount": 6227,
          "unresolvedCount": 1,
          "measuredM": 7339.2839473506065,
          "plannedCount": 5829,
          "excludedCount": 398,
          "additionalJoints": 0,
          "scope": "Straight pipes, ducts and electrical containment",
          "plans": {
            "perNetwork": {
              "costUsd": 85197.83160013771,
              "purchasedM": 6062.472,
              "requiredM": 5449.191,
              "wasteM": 613.281,
              "stockCount": 1846,
              "pieceCount": 5829,
              "kerfM": 17.487,
              "trimM": 9.23,
              "offcutM": 586.564,
              "exact": {
                "costUsd": "172660860547944074068138209/2026587500000000000000",
                "purchasedM": "757809/125",
                "requiredM": "5449191/1000",
                "wasteM": "613281/1000"
              }
            },
            "pooled": {
              "costUsd": 76846.65928856655,
              "purchasedM": 5573.268,
              "requiredM": 5449.191,
              "wasteM": 124.077,
              "stockCount": 1713,
              "pieceCount": 5829,
              "kerfM": 17.487,
              "trimM": 8.565,
              "offcutM": 98.025,
              "exact": {
                "costUsd": "311472958261935708598872509/4053175000000000000000",
                "purchasedM": "1393317/250",
                "requiredM": "5449191/1000",
                "wasteM": "124077/1000"
              }
            },
            "selected": {
              "costUsd": 76836.48071713798,
              "purchasedM": 5570.22,
              "requiredM": 5449.191,
              "wasteM": 121.029,
              "stockCount": 1712,
              "pieceCount": 5829,
              "kerfM": 17.487,
              "trimM": 8.56,
              "offcutM": 94.982,
              "exact": {
                "costUsd": "311431702730685708664881359/4053175000000000000000",
                "purchasedM": "278511/50",
                "requiredM": "5449191/1000",
                "wasteM": "121029/1000"
              }
            }
          }
        },
        {
          "id": "structure",
          "label": "Structure",
          "fileName": "str_ifc4.ifc",
          "sourceHash": "7eed88eb21dafdc5a5950d9b1ee18df3fd00fcd376a14fd1bae80658e371975e",
          "productCount": 2915,
          "segmentCount": 0,
          "measuredCount": 0,
          "unresolvedCount": 0,
          "measuredM": 0.0,
          "plannedCount": 0,
          "excludedCount": 0,
          "additionalJoints": 0,
          "scope": "Counted; no purchasing saving calculated",
          "plans": {
            "perNetwork": {
              "costUsd": 0.0,
              "purchasedM": 0.0,
              "requiredM": 0.0,
              "wasteM": 0.0,
              "stockCount": 0,
              "pieceCount": 0,
              "kerfM": 0.0,
              "trimM": 0.0,
              "offcutM": 0.0,
              "exact": {
                "costUsd": "0",
                "purchasedM": "0",
                "requiredM": "0",
                "wasteM": "0"
              }
            },
            "pooled": {
              "costUsd": 0.0,
              "purchasedM": 0.0,
              "requiredM": 0.0,
              "wasteM": 0.0,
              "stockCount": 0,
              "pieceCount": 0,
              "kerfM": 0.0,
              "trimM": 0.0,
              "offcutM": 0.0,
              "exact": {
                "costUsd": "0",
                "purchasedM": "0",
                "requiredM": "0",
                "wasteM": "0"
              }
            },
            "selected": {
              "costUsd": 0.0,
              "purchasedM": 0.0,
              "requiredM": 0.0,
              "wasteM": 0.0,
              "stockCount": 0,
              "pieceCount": 0,
              "kerfM": 0.0,
              "trimM": 0.0,
              "offcutM": 0.0,
              "exact": {
                "costUsd": "0",
                "purchasedM": "0",
                "requiredM": "0",
                "wasteM": "0"
              }
            }
          }
        }
      ],
      "trades": [
        {
          "id": "electrical",
          "label": "Electrical containment",
          "fileName": "elec_ifc4.ifc",
          "sourceHash": "8e404c4e4c9085338383a89ae57a3a31ebe96ee406214392a1bf69a6775dcecc",
          "productCount": 6305,
          "segmentCount": 84,
          "measuredCount": 80,
          "unresolvedCount": 4,
          "measuredM": 417.5140382615411,
          "plannedCount": 53,
          "excludedCount": 27,
          "additionalJoints": 0,
          "scope": "Straight pipes, ducts and electrical containment",
          "plans": {
            "perNetwork": {
              "costUsd": 3011.8958911579502,
              "purchasedM": 82.296,
              "requiredM": 50.736,
              "wasteM": 31.56,
              "stockCount": 27,
              "pieceCount": 53,
              "kerfM": 0.159,
              "trimM": 0.135,
              "offcutM": 31.266,
              "exact": {
                "costUsd": "22571195998671936909/7494016000000000",
                "purchasedM": "10287/125",
                "requiredM": "6342/125",
                "wasteM": "789/25"
              }
            },
            "pooled": {
              "costUsd": 2955.9024158304355,
              "purchasedM": 76.2,
              "requiredM": 50.736,
              "wasteM": 25.464,
              "stockCount": 25,
              "pieceCount": 53,
              "kerfM": 0.159,
              "trimM": 0.125,
              "offcutM": 25.18,
              "exact": {
                "costUsd": "22151579998671936909/7494016000000000",
                "purchasedM": "381/5",
                "requiredM": "6342/125",
                "wasteM": "3183/125"
              }
            },
            "selected": {
              "costUsd": 2955.9024158304355,
              "purchasedM": 76.2,
              "requiredM": 50.736,
              "wasteM": 25.464,
              "stockCount": 25,
              "pieceCount": 53,
              "kerfM": 0.159,
              "trimM": 0.125,
              "offcutM": 25.18,
              "exact": {
                "costUsd": "22151579998671936909/7494016000000000",
                "purchasedM": "381/5",
                "requiredM": "6342/125",
                "wasteM": "3183/125"
              }
            }
          }
        },
        {
          "id": "hvac",
          "label": "Heating & cooling",
          "fileName": "mech_ifc4.ifc",
          "sourceHash": "04a29bc312fe0b026634ad86390e8b72c1d1c1765255351f787503d3d8ce1c13",
          "productCount": 59215,
          "segmentCount": 8732,
          "measuredCount": 7944,
          "unresolvedCount": 788,
          "measuredM": 10739.702914960946,
          "plannedCount": 6480,
          "excludedCount": 1464,
          "additionalJoints": 0,
          "scope": "Straight pipes, ducts and electrical containment",
          "plans": {
            "perNetwork": {
              "costUsd": 124301.1874393761,
              "purchasedM": 5605.5768,
              "requiredM": 4365.456,
              "wasteM": 1240.1208,
              "stockCount": 2584,
              "pieceCount": 6480,
              "kerfM": 13.146,
              "trimM": 12.92,
              "offcutM": 1214.0548,
              "exact": {
                "costUsd": "52489283925962538888003/422275000000000000",
                "purchasedM": "7006971/1250",
                "requiredM": "545682/125",
                "wasteM": "1550151/1250"
              }
            },
            "pooled": {
              "costUsd": 106169.76596431047,
              "purchasedM": 4829.8608,
              "requiredM": 4365.456,
              "wasteM": 464.4048,
              "stockCount": 2220,
              "pieceCount": 6480,
              "kerfM": 13.146,
              "trimM": 11.1,
              "offcutM": 440.1588,
              "exact": {
                "costUsd": "537994055070950431489373/5067300000000000000",
                "purchasedM": "3018663/625",
                "requiredM": "545682/125",
                "wasteM": "290253/625"
              }
            },
            "selected": {
              "costUsd": 105429.06966095365,
              "purchasedM": 4819.4976,
              "requiredM": 4365.456,
              "wasteM": 454.0416,
              "stockCount": 2216,
              "pieceCount": 6480,
              "kerfM": 13.146,
              "trimM": 11.08,
              "offcutM": 429.8156,
              "exact": {
                "costUsd": "66780090586618804145497/633412500000000000",
                "purchasedM": "3012186/625",
                "requiredM": "545682/125",
                "wasteM": "283776/625"
              }
            }
          }
        },
        {
          "id": "plumbing",
          "label": "Plumbing",
          "fileName": "plumb_ifc4.ifc",
          "sourceHash": "bb53f0eb8f7295e91e0fb6ec6b79a30022a2e0e248714aab6bb1a8930c4793dd",
          "productCount": 26942,
          "segmentCount": 4308,
          "measuredCount": 4308,
          "unresolvedCount": 0,
          "measuredM": 3899.0940401076523,
          "plannedCount": 4084,
          "excludedCount": 224,
          "additionalJoints": 0,
          "scope": "Straight pipes, ducts and electrical containment",
          "plans": {
            "perNetwork": {
              "costUsd": 19686.481105042683,
              "purchasedM": 2904.744,
              "requiredM": 2631.394,
              "wasteM": 273.35,
              "stockCount": 953,
              "pieceCount": 4084,
              "kerfM": 12.252,
              "trimM": 4.765,
              "offcutM": 256.333,
              "exact": {
                "costUsd": "8138860811399/413423850",
                "purchasedM": "363093/125",
                "requiredM": "1315697/500",
                "wasteM": "5467/20"
              }
            },
            "pooled": {
              "costUsd": 17580.720828997288,
              "purchasedM": 2685.288,
              "requiredM": 2631.394,
              "wasteM": 53.894,
              "stockCount": 881,
              "pieceCount": 4084,
              "kerfM": 12.252,
              "trimM": 4.405,
              "offcutM": 37.237,
              "exact": {
                "costUsd": "29073157163597/1653695400",
                "purchasedM": "335661/125",
                "requiredM": "1315697/500",
                "wasteM": "26947/500"
              }
            },
            "selected": {
              "costUsd": 17570.542257568715,
              "purchasedM": 2682.24,
              "requiredM": 2631.394,
              "wasteM": 50.846,
              "stockCount": 880,
              "pieceCount": 4084,
              "kerfM": 12.252,
              "trimM": 4.4,
              "offcutM": 34.194,
              "exact": {
                "costUsd": "4150903558121/236242200",
                "purchasedM": "67056/25",
                "requiredM": "1315697/500",
                "wasteM": "25423/500"
              }
            }
          }
        },
        {
          "id": "sprinkler",
          "label": "Sprinklers",
          "fileName": "sprinkle_ifc4.ifc",
          "sourceHash": "0e30c25a77ebcd75b2fc3a6cb87dc3891bd476f60a269e36eb5e0149bcc06ea7",
          "productCount": 38255,
          "segmentCount": 6228,
          "measuredCount": 6227,
          "unresolvedCount": 1,
          "measuredM": 7339.2839473506065,
          "plannedCount": 5829,
          "excludedCount": 398,
          "additionalJoints": 0,
          "scope": "Straight pipes, ducts and electrical containment",
          "plans": {
            "perNetwork": {
              "costUsd": 85197.83160013771,
              "purchasedM": 6062.472,
              "requiredM": 5449.191,
              "wasteM": 613.281,
              "stockCount": 1846,
              "pieceCount": 5829,
              "kerfM": 17.487,
              "trimM": 9.23,
              "offcutM": 586.564,
              "exact": {
                "costUsd": "172660860547944074068138209/2026587500000000000000",
                "purchasedM": "757809/125",
                "requiredM": "5449191/1000",
                "wasteM": "613281/1000"
              }
            },
            "pooled": {
              "costUsd": 76846.65928856655,
              "purchasedM": 5573.268,
              "requiredM": 5449.191,
              "wasteM": 124.077,
              "stockCount": 1713,
              "pieceCount": 5829,
              "kerfM": 17.487,
              "trimM": 8.565,
              "offcutM": 98.025,
              "exact": {
                "costUsd": "311472958261935708598872509/4053175000000000000000",
                "purchasedM": "1393317/250",
                "requiredM": "5449191/1000",
                "wasteM": "124077/1000"
              }
            },
            "selected": {
              "costUsd": 76836.48071713798,
              "purchasedM": 5570.22,
              "requiredM": 5449.191,
              "wasteM": 121.029,
              "stockCount": 1712,
              "pieceCount": 5829,
              "kerfM": 17.487,
              "trimM": 8.56,
              "offcutM": 94.982,
              "exact": {
                "costUsd": "311431702730685708664881359/4053175000000000000000",
                "purchasedM": "278511/50",
                "requiredM": "5449191/1000",
                "wasteM": "121029/1000"
              }
            }
          }
        }
      ],
      "provenance": {
        "campaignId": "3d9c5dc8a37b41f78b7a2233b2cb5c2d",
        "runId": "b2a02149223347f9b984caf7e48f9052",
        "reportPath": "evidence/benchmarks/hospital-whole-procurement/3d9c5dc8a37b41f78b7a2233b2cb5c2d/campaign/report.json",
        "reportSha256": "b4c59735b778250f8fe7438a12fb92c65425c1d4f1e4783012fc8bf63bf4168a",
        "planRoot": "00a5f38955c4d9765dae36334e80633f2067ba78f5cf8a795de8a752b935262f",
        "requestRoot": "753ab07900d28eee3b26951e464de432750e9b679ea6a961cdcd2dc5d36c8360",
        "baseRoot": "a8fda28065ccee823176259e687bbbfee1d0044888329f250e7bdfe4050982cb",
        "packetRoot": "275a726bd26458ab8c45ce6687af7cca9bcd46551a472399b300bce6dab52036"
      }
    }
  },
  "review": {
    "status": "Code compliance not established",
    "constructionApproved": false,
    "geometryChanged": false,
    "wholeBuildingRedesigned": false,
    "arithmeticVerified": true,
    "additionalJoints": 3457,
    "smallTailCount": 149,
    "smallTailThresholdMm": 100,
    "smallestTailMm": 3,
    "date": "2026-10-22",
    "summary": "The purchasing arithmetic was independently checked. Product specifications, joint details and engineering approval remain unresolved.",
    "notes": [
      "149 new pieces are shorter than 100 mm, including a 3 mm duct piece. The 100 mm screening threshold is not a code limit.",
      "Materials, governing code, ventilation requirements, electrical circuits, sprinkler hydraulics and structural calculations are unverified.",
      "The no-added-joints plan leaves 2,113 overlength spans unplanned. It is not cleared for construction."
    ],
    "reportPath": "evidence/benchmarks/hospital-code-review/20261022/review.json",
    "reportSha256": "f8f586adc084bc3b07a31b9ef04c4c7830ab2ee456732df1b5555b7c2e2b0cba"
  },
  "priceNote": "Estimated gross straight-material savings using public reference prices. Excludes labor, added joints, fittings, equipment, tax and freight. Product and installation requirements can reduce or erase the estimate.",
  "scenarioNote": "The two plans include different quantities. Their savings cannot be added and their total costs are not comparable as complete building designs.",
  "provenance": {
    "checkerVersion": "oma-independent-checker/2:1ccc8728fbf6ba0ad1bbb16b2dd339896e8bb292b03e08754e3b1b93156b48c6",
    "priceDate": "2026-10-22",
    "dataType": "Retained whole-hospital purchasing runs",
    "source": "Open IFC Model Repository / IFC-Bench",
    "license": "CC BY 3.0",
    "sourceUrl": "https://openifcmodel.cs.auckland.ac.nz/"
  }
};

// The fabrication assumptions are identical in each scenario's before and after
// plans. Joining more pieces is not counted as an optimization saving.
for (const scenario of Object.values(hospital.scenarios)) {
  scenario.plannedOriginalSegments = scenario.plannedCount;
  scenario.excludedOverlengthSegments = scenario.excludedCount;
  scenario.assumedJoints = scenario.additionalJoints;
  scenario.coverage = {
    ...hospital.coverage,
    plannedOriginalSegments: scenario.plannedCount,
    excludedOverlengthSegments: scenario.excludedCount,
  };
  scenario.jointNote = "The same assumed joints are included in both the before and after purchasing plans.";
}
hospital.sourceCounts = Object.fromEntries(hospital.scenarios.broad.sources.map(source => [source.id, source.productCount]));

/** Compare the same included demand under a selected purchasing baseline.
 * Returns {scenarioId, baselineId, disciplineId, before, after, savings, scope}.
 * before/after: costUsd, purchasedM, requiredM, wasteM, stockCount, pieceCount.
 * savings: costUsd, costPercent, purchasedM, purchasedPercent, wasteM,
 * wastePercent, stockCount. Percent values are on a 0..100 scale.
 * disciplineId may be all or any of the seven source IDs; unpriced sources
 * return zero quantities and null percentages. Unknown IDs throw.
 */
export function comparison(scenarioId = "broad", baselineId = "perNetwork", disciplineId = "all") {
  const scenario = hospital.scenarios[scenarioId];
  if (!scenario) throw new RangeError(`Unknown hospital scenario: ${scenarioId}`);
  if (!hospital.baselines.some(item => item.id === baselineId)) throw new RangeError(`Unknown baseline: ${baselineId}`);
  const source = disciplineId === "all" ? scenario : scenario.sources.find(item => item.id === disciplineId);
  if (!source) throw new RangeError(`Unknown discipline: ${disciplineId}`);
  const before = source.plans[baselineId];
  const after = source.plans.selected;
  const percent = (difference, total) => total > 0 ? difference / total * 100 : null;
  const costUsd = before.costUsd - after.costUsd;
  const purchasedM = before.purchasedM - after.purchasedM;
  const wasteM = before.wasteM - after.wasteM;
  return {
    scenarioId, baselineId, disciplineId, before, after,
    savings: {
      costUsd, costPercent: percent(costUsd, before.costUsd),
      purchasedM, purchasedPercent: percent(purchasedM, before.purchasedM),
      wasteM, wastePercent: percent(wasteM, before.wasteM),
      stockCount: before.stockCount - after.stockCount,
    },
    scope: disciplineId === "all" ? hospital.coverage.description : source.scope,
  };
}

export default hospital;
