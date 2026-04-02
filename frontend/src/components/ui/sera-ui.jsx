import { useEffect, useRef, useState } from "react";
import { motion, useInView, useSpring, useTransform } from "framer-motion";

// Animated Counter Component
export function AnimatedCounter({ value, duration = 2, className = "" }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true });
  const spring = useSpring(0, { duration: duration * 1000 });
  const display = useTransform(spring, (current) =>
    Math.round(current).toLocaleString("en-IN")
  );
  const [displayValue, setDisplayValue] = useState("0");

  useEffect(() => {
    if (isInView) {
      spring.set(value);
    }
  }, [isInView, value, spring]);

  useEffect(() => {
    return display.on("change", (latest) => {
      setDisplayValue(latest);
    });
  }, [display]);

  return (
    <span ref={ref} className={className}>
      {displayValue}
    </span>
  );
}

// Animated Stats Card
export function StatsCard({
  title,
  value,
  prefix = "",
  suffix = "",
  icon: Icon,
  trend,
  trendLabel,
  color = "primary",
  delay = 0,
}) {
  const colors = {
    primary: {
      bg: "bg-primary/10",
      text: "text-primary",
      glow: "hover:shadow-[0_0_30px_rgba(191,255,0,0.15)]",
    },
    emerald: {
      bg: "bg-emerald-500/10",
      text: "text-emerald-500",
      glow: "hover:shadow-[0_0_30px_rgba(16,185,129,0.15)]",
    },
    amber: {
      bg: "bg-amber-500/10",
      text: "text-amber-500",
      glow: "hover:shadow-[0_0_30px_rgba(245,158,11,0.15)]",
    },
    rose: {
      bg: "bg-lime-500/10",
      text: "text-lime-500",
      glow: "hover:shadow-[0_0_30px_rgba(244,63,94,0.15)]",
    },
  };

  const colorSet = colors[color] || colors.primary;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay }}
      whileHover={{ y: -4, transition: { duration: 0.2 } }}
      className={`relative overflow-hidden rounded-2xl bg-card border border-border/50 p-6 ${colorSet.glow} transition-all duration-300`}
    >
      {/* Gradient Overlay */}
      <div className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent pointer-events-none" />
      
      {/* Content */}
      <div className="relative z-10">
        <div className="flex items-center justify-between mb-4">
          <span className="text-sm font-medium text-muted-foreground">
            {title}
          </span>
          {Icon && (
            <div className={`w-10 h-10 rounded-xl ${colorSet.bg} flex items-center justify-center`}>
              <Icon className={`w-5 h-5 ${colorSet.text}`} strokeWidth={1.5} />
            </div>
          )}
        </div>
        
        <div className="flex items-end gap-2">
          <span className={`font-serif text-4xl font-semibold tracking-tight ${colorSet.text}`}>
            {prefix}
            <AnimatedCounter value={value} />
            {suffix}
          </span>
        </div>

        {trend !== undefined && (
          <div className="mt-3 flex items-center gap-2">
            <span
              className={`text-xs font-medium px-2 py-1 rounded-full ${
                trend >= 0
                  ? "bg-emerald-500/10 text-emerald-500"
                  : "bg-red-500/10 text-red-500"
              }`}
            >
              {trend >= 0 ? "+" : ""}
              {trend}%
            </span>
            {trendLabel && (
              <span className="text-xs text-muted-foreground">{trendLabel}</span>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
}

// Bento Grid Container
export function BentoGrid({ children, className = "" }) {
  return (
    <div className={`grid gap-4 ${className}`}>
      {children}
    </div>
  );
}

// Bento Grid Item
export function BentoItem({
  children,
  className = "",
  colSpan = 1,
  rowSpan = 1,
  delay = 0,
}) {
  const colClasses = {
    1: "col-span-1",
    2: "col-span-1 md:col-span-2",
    3: "col-span-1 md:col-span-3",
    4: "col-span-1 md:col-span-4",
  };

  const rowClasses = {
    1: "row-span-1",
    2: "row-span-1 md:row-span-2",
    3: "row-span-1 md:row-span-3",
  };

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4, delay }}
      className={`${colClasses[colSpan]} ${rowClasses[rowSpan]} ${className}`}
    >
      {children}
    </motion.div>
  );
}

// Animated Progress Bar
export function AnimatedProgress({ value, max = 100, color = "primary", className = "" }) {
  const percentage = (value / max) * 100;
  
  const colors = {
    primary: "bg-primary",
    emerald: "bg-emerald-500",
    amber: "bg-amber-500",
    rose: "bg-lime-500",
  };

  return (
    <div className={`h-2 rounded-full bg-muted overflow-hidden ${className}`}>
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${percentage}%` }}
        transition={{ duration: 1, ease: "easeOut" }}
        className={`h-full rounded-full ${colors[color]}`}
      />
    </div>
  );
}

// Glowing Card
export function GlowCard({ children, className = "", glowColor = "rose" }) {
  const glowColors = {
    rose: "hover:shadow-[0_0_40px_rgba(191,255,0,0.2)]",
    emerald: "hover:shadow-[0_0_40px_rgba(16,185,129,0.2)]",
    amber: "hover:shadow-[0_0_40px_rgba(245,158,11,0.2)]",
  };

  return (
    <motion.div
      whileHover={{ y: -4 }}
      transition={{ duration: 0.2 }}
      className={`relative overflow-hidden rounded-2xl bg-card border border-border/50 p-6 transition-all duration-300 ${glowColors[glowColor]} ${className}`}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent pointer-events-none" />
      <div className="relative z-10">{children}</div>
    </motion.div>
  );
}

// Shimmer Effect
export function ShimmerText({ children, className = "" }) {
  return (
    <motion.span
      className={`relative inline-block ${className}`}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      <span className="relative z-10">{children}</span>
      <motion.span
        className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent"
        initial={{ x: "-100%" }}
        animate={{ x: "100%" }}
        transition={{ repeat: Infinity, duration: 2, ease: "linear" }}
      />
    </motion.span>
  );
}

// Animated List Item
export function AnimatedListItem({ children, index = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3, delay: index * 0.1 }}
    >
      {children}
    </motion.div>
  );
}

// Pulse Dot
export function PulseDot({ color = "emerald", className = "" }) {
  const colors = {
    emerald: "bg-emerald-500",
    rose: "bg-lime-500",
    amber: "bg-amber-500",
    primary: "bg-primary",
  };

  return (
    <span className={`relative flex h-3 w-3 ${className}`}>
      <span
        className={`animate-ping absolute inline-flex h-full w-full rounded-full ${colors[color]} opacity-75`}
      />
      <span className={`relative inline-flex rounded-full h-3 w-3 ${colors[color]}`} />
    </span>
  );
}

// Chart Container with Animation
export function ChartContainer({ children, title, className = "", delay = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay }}
      className={`rounded-2xl bg-card border border-border/50 p-6 ${className}`}
    >
      {title && (
        <h3 className="font-serif text-xl font-semibold mb-6">{title}</h3>
      )}
      {children}
    </motion.div>
  );
}

// Stat Badge
export function StatBadge({ label, value, trend, className = "" }) {
  const isPositive = trend >= 0;
  
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      className={`inline-flex items-center gap-3 px-4 py-2 rounded-full bg-muted/50 border border-border/50 ${className}`}
    >
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="font-serif font-semibold">{value}</span>
      {trend !== undefined && (
        <span
          className={`text-xs font-medium ${
            isPositive ? "text-emerald-500" : "text-red-500"
          }`}
        >
          {isPositive ? "↑" : "↓"} {Math.abs(trend)}%
        </span>
      )}
    </motion.div>
  );
}
