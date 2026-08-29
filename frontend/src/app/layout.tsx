import React from "react"
import "./globals.css"
import NavBar from "./NavBar"

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <head>
        <title>Campus Lost & Found Intelligence System</title>
        <meta name="description" content="Find your lost items on campus" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </head>
      <body>
        <NavBar />
        <main className="page-shell">
          {children}
        </main>
      </body>
    </html>
  )
}
