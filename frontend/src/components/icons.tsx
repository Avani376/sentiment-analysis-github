/** Icon re-exports (lucide) plus the SENTINEX logo mark. */

export {
  Activity,
  Boxes,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Database,
  FileUp,
  Gauge,
  ListFilter,
  MessageSquareText,
  Microscope,
  Scale,
  Search,
  Send,
  Sparkles,
  Timer,
  XCircle,
} from "lucide-react";

import type { SVGProps } from "react";

export function SentinexLogo(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <defs>
        <linearGradient id="sentinex-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#6366f1" />
          <stop offset="1" stopColor="#a855f7" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill="url(#sentinex-g)" />
      <path
        d="M9 20c2-8 5-11 7-11s5 3 7 11"
        stroke="white"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
      <circle cx="16" cy="21" r="2.4" fill="white" />
    </svg>
  );
}
