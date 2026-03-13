"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "./auth-provider";

function navClassName(pathname: string, href: string) {
  return pathname === href ? "nav-link nav-link-active" : "nav-link";
}

export function SiteHeader() {
  const pathname = usePathname();
  const { isReady, user, logout } = useAuth();

  return (
    <header className="site-header">
      <Link className="brand" href="/">
        <span className="brand-mark">M</span>
        <span className="brand-copy">
          <strong>Midas</strong>
          <span>Local reflection workspace</span>
        </span>
      </Link>

      <nav className="nav-links" aria-label="Primary">
        <Link className={navClassName(pathname, "/")} href="/">
          Overview
        </Link>
        <Link className={navClassName(pathname, "/login")} href="/login">
          Login
        </Link>
        <Link className={navClassName(pathname, "/chat")} href="/chat">
          Chat
        </Link>
      </nav>

      <div className="auth-controls">
        {user ? (
          <>
            <span className="session-pill">{user.email}</span>
            <button className="ghost-button" onClick={logout} type="button">
              Log out
            </button>
          </>
        ) : (
          <span className="session-pill">{isReady ? "Signed out" : "Loading session"}</span>
        )}
      </div>
    </header>
  );
}
