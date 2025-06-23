GAME_VERSIONS = {
    1005 : [
        "0.0.0-alpha1",
        "0.0.0-alpha2",
        "0.0.0-alpha3"
    ],
    1008 : [
        "0.0.0-alpha4"
    ],
    1009 : [
        "0.0.0-alpha5"
    ],
    1013 : [
        "0.0.0-alpha6"
    ],
    1015 : [
        "0.0.0-alpha6.1",
        "0.0.0-alpha6.2"
    ],
    1018 : [
        "0.0.0-alpha7"
    ],
    1019 : [
        "0.0.0-alpha7.1",
        "0.0.0-alpha7.2",
        "0.0.0-alpha7.3"
    ],
    1022 : [
        "0.0.0-alpha7.4"
    ],
    1024 : [
        "0.0.0-alpha8"
    ],
    1027 : [
        "0.0.0-alpha9",
        "0.0.0-alpha10",
        "0.0.0-alpha10.1",
        "0.0.0-alpha10.2"
    ],
    1029 : [
        "0.0.0-alpha11"
    ],
    1030 : [
        "0.0.0-alpha12-demo",
        "0.0.0-alpha12"
    ],
    1031 : [
        "0.0.0-alpha13-demo",
        "0.0.0-alpha13",
        "0.0.0-alpha13.5-demo",
        "0.0.0-alpha13.6-demo",
        "0.0.0-alpha13.7-demo",
        "0.0.0-alpha14-demo",
        "0.0.0-alpha14.1-demo"
    ],
    1032 : [
        "0.0.0-alpha14.2-demo",
        "0.0.0-alpha14.3-demo",
        "0.0.0-alpha15-demo",
        "0.0.0-alpha15.1-demo",
        "0.0.0-alpha15.2-demo",
        "0.0.0-alpha15.3-demo"
    ],
    1033 : [
        "0.0.0-alpha15.2",
        "0.0.0-alpha15.3-demo"
    ],
    1036 : [
        "0.0.0-alpha16"
    ],
    1038 : [
        "0.0.0-alpha16",
        "0.0.0-alpha16.1"
    ],
    1040 : [
        "0.0.0-alpha17"
    ],
    1042 : [
        "0.0.0-alpha18"
    ],
    1045 : [
        "0.0.0-alpha19"
    ],
    1057 : [
        "0.0.0-alpha20"
    ],
    1064 : [
        "0.0.0-alpha21",
        "0.0.0-alpha21.1"
    ],
    1067 : [
        "0.0.0-alpha22.2"
    ],
    1071 : [
        "0.0.0-alpha22.3",
        "0.0.0-alpha22.4"
    ],
    99999 : [
        "0.0.0-alpha22.4"
    ],
    1082 : [
        "0.0.0-alpha23",
        "0.0.0-alpha23.1"
    ],
    1088 : [
        "0.0.0-alpha23.2"
    ],
    1089 : [
        "0.0.1"
    ],
    1091 : [
        "0.0.2"
    ],
    1094 : [
        "0.0.3",
        "0.0.4",
        "0.0.5"
    ],
    1095 : [
        "0.0.6",
        "0.0.7",
        "0.0.8",
        "0.0.8-rc2",
        "0.0.8-rc3"
    ],
    1103 : [
        "0.0.9-rc1"
    ],
    1105 : [
        "0.0.9-rc2",
        "0.0.9-rc3",
        "0.0.9-rc4",
        "0.0.9-rc5",
        "0.0.9-rc6",
        "0.0.9-rc7"
    ],
    1118 : [
        "0.1.0-pre1-rc3"
    ],
    1119 : [
        "0.1.0-pre2-rc1",
        "0.1.0-pre2-rc2"
    ],
    1121 : [
        "0.1.0-pre3-rc1",
        "0.1.0-pre4-rc1"
    ],
    1122 : [
        "0.1.0-pre5-rc1",
        "0.1.0-pre6-rc1",
        "0.1.0-pre7-rc1",
        "0.1.0-pre8-rc1",
        "0.1.1"
    ]
}
LATEST_GAME_VERSION = list(GAME_VERSIONS.keys())[-1]
LATEST_MAJOR_VERSION = 3

BP_VERSION_REACTION_A = "\U0001f1e6"
BP_VERSION_REACTION_C = "\U0001f1e8"
BP_VERSION_REACTION_D = "\U0001f1e9"
BP_VERSION_REACTION_P = "\U0001f1f5"
BP_VERSION_REACTION_R = "\U0001f1f7"
BP_VERSION_REACTION_DOT_1 = "\u23fa"
BP_VERSION_REACTION_DOT_2 = 1261037521496965202
BP_VERSION_REACTION_DOT_3 = 1333165681281339503
BP_VERSION_REACTION_DIGITS:list[dict[str,str|int]] = [
    {str(i) : f"{i}\ufe0f\u20e3" for i in range(10)},
    {str(i) : v for i,v in enumerate([
        1159909769876877352,1159909772133400707,1159909773643358228,
        1159909775526592512,1159909784305283133,1159909786956087326,
        1159909788130476124,1159909789741105282,1159909792106676405,
        1159909793578877028
    ])},
    {str(i) : v for i,v in enumerate([
        1159909533074866286,1159909535872471162,1159909537944457226,
        1159909542193270824,1159909546735702108,1159909549323587757,
        1159909551697576056,1159909554532913203,1159909556336468008,
        1159909559066964110
    ])},
    {str(i) : v for i,v in enumerate([
        1333173576563687516,1333173578148876319,1333173580166463569,
        1333173581474959372,1333173589674954832,1333173591365255329,
        1333173593269469244,1333173594930413579,1333173596901867530,
        1333173598407626752
    ])},
    {str(i) : v for i,v in enumerate([
        1333173698345177138,1333173700429746297,1333173701830643847,
        1333173704078921842,1333173705756512297,1333173708008849540,
        1333173709531250708,1333173712148627516,1333173713822286006,
        1333173715554275430
    ])},
    {str(i) : v for i,v in enumerate([
        1333173795329933424,1333173796936482897,1333173798458888262,
        1333173800145129523,1333173801659400326,1333173803358093393,
        1333173805409107968,1333173807095218248,1333173808609361940,
        1333173811171954800
    ])}
]

def _getDecomposedVersionId(versionId:str) -> dict[str,list[str]|list[dict]]:

    mainNumber, *suffixes = versionId.split("-")

    output:dict[str,list[str]|list[dict]] = {
        "main" : mainNumber.split("."),
        "suffixes" : []
    }

    for suffix in suffixes:

        if suffix.startswith("alpha"):
            suffixNumSplit = suffix.removeprefix("alpha").split(".")
            suffixNumOutput = [[c for c in suffixNumSplit[0]]]
            if len(suffixNumSplit) > 1:
                suffixNumOutput.append(suffixNumSplit[1])
            output["suffixes"].append({
                "type" : "alpha",
                "num" : suffixNumOutput
            })

        elif suffix.startswith("rc"):
            output["suffixes"].append({
                "type" : "rc",
                "num" : suffix.removeprefix("rc")
            })

        elif suffix.startswith("pre"):
            output["suffixes"].append({
                "type" : "preview",
                "num" : suffix.removeprefix("pre")
            })

        elif suffix == "demo":
            output["suffixes"].append({"type":"demo"})

    return output

def versionNumToText(version:int,returnAll:bool=False) -> None|str|list[str]:

    versionTexts = GAME_VERSIONS.get(version)

    if versionTexts is None:
        return None

    if not returnAll:
        versionTexts = [versionTexts[-1]]

    outputs = []
    for versionText in versionTexts:
        output = ""

        decomposed = _getDecomposedVersionId(versionText)

        output += ".".join(decomposed["main"])

        for suffix in decomposed["suffixes"]:

            if suffix["type"] == "alpha":
                output += " Alpha "
                output += "".join(suffix["num"][0])
                if len(suffix["num"]) > 1:
                    output += "." + suffix["num"][1]

            elif suffix["type"] == "rc":
                output += " RC "
                output += suffix["num"]

            elif suffix["type"] == "preview":
                output += " Preview "
                output += suffix["num"]

            elif suffix["type"] == "demo":
                output += " Demo"

        outputs.append(output)

    if returnAll:
        return outputs

    return outputs[0]

def versionNumToReactions(version:int) -> None|list[str|int]:

    versionTexts = GAME_VERSIONS.get(version)

    if versionTexts is None:
        return None

    versionText = versionTexts[-1]

    decomposed = _getDecomposedVersionId(versionText)

    output = [
        BP_VERSION_REACTION_DIGITS[0][decomposed["main"][0]],
        BP_VERSION_REACTION_DOT_1,
        BP_VERSION_REACTION_DIGITS[1][decomposed["main"][1]],
        BP_VERSION_REACTION_DOT_2,
        BP_VERSION_REACTION_DIGITS[2][decomposed["main"][2]]
    ]

    digitsIndex = 3

    for suffix in decomposed["suffixes"]:

        if suffix["type"] == "alpha":
            output.append(BP_VERSION_REACTION_A)
            for num in suffix["num"][0]:
                output.append(BP_VERSION_REACTION_DIGITS[digitsIndex][num])
                digitsIndex += 1
            if len(suffix["num"]) > 1:
                output.append(BP_VERSION_REACTION_DOT_3)
                output.append(BP_VERSION_REACTION_DIGITS[digitsIndex][suffix["num"][1]])
                digitsIndex += 1

        elif suffix["type"] == "rc":
            output.extend([BP_VERSION_REACTION_R,BP_VERSION_REACTION_C])
            output.append(BP_VERSION_REACTION_DIGITS[digitsIndex][suffix["num"]])
            digitsIndex += 1

        elif suffix["type"] == "preview":
            output.append(BP_VERSION_REACTION_P)
            output.append(BP_VERSION_REACTION_DIGITS[digitsIndex][suffix["num"]])
            digitsIndex += 1

        elif suffix["type"] == "demo":
            output.append(BP_VERSION_REACTION_D)

    return output