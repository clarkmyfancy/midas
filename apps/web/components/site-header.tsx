"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

function navClassName(pathname: string, href: string) {
  return pathname === href ? "app-toggle app-toggle-active" : "app-toggle";
}

export function SiteHeader() {
  const pathname = usePathname();
  if (!pathname || !["/", "/reflect", "/profile", "/chat", "/memory"].includes(pathname)) {
    return null;
  }

  return (
    <header className="site-header app-header">
      <nav className="app-switcher" aria-label="Application">
        <Link className={navClassName(pathname, "/")} href="/">
          Reflect
        </Link>
        <Link className={navClassName(pathname, "/memory")} href="/memory">
          Memory
        </Link>
      </nav>

      <Link
        aria-label="Profile"
        className={pathname === "/profile" ? "profile-trigger profile-trigger-active" : "profile-trigger"}
        href="/profile"
      >
        <svg aria-hidden="true" className="profile-icon" viewBox="0 0 24 24">
          <path
            d="M12 12a4 4 0 1 0-4-4 4 4 0 0 0 4 4Zm0 2c-3.86 0-7 2.24-7 5v1h14v-1c0-2.76-3.14-5-7-5Z"
            fill="currentColor"
          />
        </svg>
      </Link>
    </header>
  );
}
