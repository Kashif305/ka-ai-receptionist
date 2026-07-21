import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Samina Beauty Salon | Owner Dashboard",
  description: "Owner dashboard powered by KA AI Receptionist",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
