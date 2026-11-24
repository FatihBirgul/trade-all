import React from "react";
import { View } from "react-native";
import Svg, { Polyline, Defs, LinearGradient, Stop, Polygon } from "react-native-svg";

import { colors } from "@/src/theme";

interface Props {
  data?: number[];
  width?: number;
  height?: number;
  color?: string;
  fill?: boolean;
  testID?: string;
}

export function Sparkline({ data, width = 120, height = 40, color, fill = true, testID }: Props) {
  if (!data || data.length < 2) {
    return <View style={{ width, height }} testID={testID} />;
  }
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const stepX = width / (data.length - 1);
  const pad = 3;
  const usableH = height - pad * 2;

  const points = data
    .map((d, i) => {
      const x = i * stepX;
      const y = pad + usableH - ((d - min) / range) * usableH;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");

  const stroke = color || (data[data.length - 1] >= data[0] ? colors.success : colors.error);
  const areaPoints = `0,${height} ${points} ${width},${height}`;

  return (
    <Svg width={width} height={height} testID={testID}>
      <Defs>
        <LinearGradient id="spark-fill" x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0" stopColor={stroke} stopOpacity="0.28" />
          <Stop offset="1" stopColor={stroke} stopOpacity="0" />
        </LinearGradient>
      </Defs>
      {fill && <Polygon points={areaPoints} fill="url(#spark-fill)" />}
      <Polyline points={points} fill="none" stroke={stroke} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
    </Svg>
  );
}
