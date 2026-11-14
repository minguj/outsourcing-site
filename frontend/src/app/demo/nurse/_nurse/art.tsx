import type { ArtKey, ImageItem } from "./data";

// 사진 자리: 실제 사진 대신 직접 그린 선 일러스트(저작권 문제 없음).
// 실제 구축 시에는 센터가 제공한 사진으로 바뀐다.
const TONES: Record<ArtKey, [string, string]> = {
  home: ["#e9efe9", "#3d6b5c"], care: ["#f3ece3", "#8a5a3b"], walk: ["#e6edf1", "#3c5d73"], pill: ["#f1ede4", "#6f6235"],
  team: ["#ebe9f0", "#4f4a6e"], wound: ["#f2e8e6", "#8b4b45"], talk: ["#e8eee8", "#4a6a4a"], tube: ["#e7eeef", "#3f6468"],
};

function Shapes({ k }: { k: ArtKey }) {
  switch (k) {
    case "home": return <>
      <path d="M40 132V78l50-40 50 40v54" /><path d="M76 132v-30h28v30" /><path d="M150 132h50" />
      <circle cx="176" cy="62" r="10" /><path d="M176 72v34m-14-22h28m-24 48 10-26 10 26" /><path d="M188 96h14v20h-14z" />
    </>;
    case "care": return <>
      <circle cx="78" cy="58" r="13" /><path d="M58 132c0-28 9-46 20-46s20 18 20 46" />
      <circle cx="152" cy="62" r="13" /><path d="M132 132c0-26 9-44 20-44s20 18 20 44" />
      <path d="M98 100h22a10 10 0 0 1 10 10v4" /><rect x="112" y="96" width="18" height="12" rx="3" /><path d="M120 108c0 10-8 12-8 20" />
    </>;
    case "walk": return <>
      <circle cx="92" cy="52" r="11" /><path d="M92 63v36l-12 32m12-32 14 32m-14-58-18 18m18-18 16 14" /><path d="M72 81v52" />
      <circle cx="142" cy="50" r="11" /><path d="M142 61v38l-10 32m10-32 12 32m-12-58-20 14" /><path d="M30 132h180" />
    </>;
    case "pill": return <>
      <rect x="40" y="70" width="160" height="50" rx="8" />{[1, 2, 3, 4, 5, 6].map(i => <path key={i} d={`M${(40 + i * 160 / 7).toFixed(1)} 70v50`} />)}
      {[0, 2, 4, 6].map(i => <circle key={i} cx={(40 + (i + 0.5) * 160 / 7).toFixed(1)} cy="95" r="4" />)}
      <rect x="96" y="30" width="44" height="22" rx="11" /><path d="M118 30v22" />
    </>;
    case "team": return <>
      {[60, 100, 140, 180].map((x, i) => <g key={x}><circle cx={x} cy={i % 2 ? 62 : 58} r="12" /><path d={`M${x - 20} 132c0-30 9-${i % 2 ? 46 : 50} 20-${i % 2 ? 46 : 50}s20 ${i % 2 ? 16 : 20} 20 ${i % 2 ? 46 : 50}`} /></g>)}
    </>;
    case "wound": return <>
      <rect x="54" y="62" width="132" height="44" rx="22" transform="rotate(-12 120 84)" /><rect x="96" y="66" width="48" height="36" rx="4" transform="rotate(-12 120 84)" />
      <path d="M40 132h60M140 132h60" /><circle cx="72" cy="40" r="3" /><circle cx="170" cy="120" r="3" />
    </>;
    case "talk": return <>
      <path d="M44 48h80a10 10 0 0 1 10 10v30a10 10 0 0 1-10 10H78l-18 14v-14H44a10 10 0 0 1-10-10V58a10 10 0 0 1 10-10Z" />
      <path d="M196 70h-50a10 10 0 0 0-10 10v24a10 10 0 0 0 10 10h28l14 12v-12h8a10 10 0 0 0 10-10V80a10 10 0 0 0-10-10Z" />
      <path d="M56 70h56M56 82h36M152 88h32M152 100h20" />
    </>;
    case "tube": return <>
      <path d="M70 40v30c0 20 30 20 30 40v22" /><circle cx="70" cy="34" r="6" />
      <rect x="132" y="60" width="44" height="64" rx="8" /><path d="M132 82h44M154 46v14" /><path d="M100 132h100" />
    </>;
  }
}

export function Art({ k, className, label }: { k: ArtKey; className?: string; label?: string }) {
  const [bg, ink] = TONES[k];
  return <svg className={"nc-art " + (className ?? "")} viewBox="0 0 240 160" preserveAspectRatio="xMidYMid slice" role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true} style={{ background: bg }}>
    <g fill="none" stroke={ink} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" opacity=".78"><Shapes k={k} /></g>
  </svg>;
}

/** 이미지 라이브러리 항목을 그린다. 기본 일러스트는 Art, 올린 사진은 img. */
export function Pic({ img, className, fallback = "home" }: { img: ImageItem | undefined; className?: string; fallback?: ArtKey }) {
  if (!img) return <Art k={fallback} className={className} />;
  if (img.src.startsWith("art:")) return <Art k={img.src.slice(4) as ArtKey} className={className} label={img.alt} />;
  // eslint-disable-next-line @next/next/no-img-element -- 사용자가 올린 data URL이라 next/image 최적화를 쓸 수 없다
  return <img className={"nc-art " + (className ?? "")} src={img.src} alt={img.alt} />;
}
