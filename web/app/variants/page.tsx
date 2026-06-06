import Link from "next/link";
import { ArrowRight, Gauge, Landmark, Smartphone, Table2 } from "lucide-react";

const variants = [
  {
    href: "/",
    name: "A. Control Plane",
    tag: "Current baseline",
    description: "Balanced desktop and mobile asset cockpit, built around total assets, account cards, broker status, and grouped positions.",
    icon: Gauge,
  },
  {
    href: "/variants/command",
    name: "B. Command Desk",
    tag: "Dark operator",
    description: "A trader-style control room with a persistent risk rail, market/account split, and high-contrast execution posture.",
    icon: Landmark,
  },
  {
    href: "/variants/ledger",
    name: "C. Ledger Sheet",
    tag: "Dense finance",
    description: "A calm accounting-led layout for people who trust rows, deltas, currency separation, and audit-like hierarchy.",
    icon: Table2,
  },
  {
    href: "/variants/mobile",
    name: "D. Mobile Native",
    tag: "Phone first",
    description: "A mobile app-like dashboard optimized for one-handed account scanning, quick holdings review, and draft entry.",
    icon: Smartphone,
  },
];

export default function VariantsPage() {
  return (
    <main className="variantHub">
      <div className="variantHero">
        <span className="eyebrow">Design shotgun</span>
        <h1>BrokerGate dashboard directions</h1>
        <p>
          Four ways to express the same product: one control plane for every brokerage
          account you own. Pick the direction that best matches the company you want this
          to feel like.
        </p>
      </div>

      <div className="variantGrid">
        {variants.map((variant) => {
          const Icon = variant.icon;
          return (
            <Link className="variantTile" href={variant.href} key={variant.href}>
              <div className="variantTileTop">
                <span className="variantIcon">
                  <Icon />
                </span>
                <span className="pill blue">{variant.tag}</span>
              </div>
              <h2>{variant.name}</h2>
              <p>{variant.description}</p>
              <span className="variantOpen">
                Open direction <ArrowRight />
              </span>
            </Link>
          );
        })}
      </div>
    </main>
  );
}
