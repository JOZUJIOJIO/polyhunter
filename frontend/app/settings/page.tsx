"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Settings, Shield, Bell, Key } from "lucide-react";

function SettingRow({ label, description, defaultValue, unit }: {
  label: string;
  description: string;
  defaultValue: string;
  unit?: string;
}) {
  return (
    <div className="flex items-center justify-between py-3">
      <div>
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      <div className="flex items-center gap-2">
        <Input defaultValue={defaultValue} className="w-20 text-right" />
        {unit && <span className="text-sm text-muted-foreground w-8">{unit}</span>}
      </div>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <div className="space-y-6 max-w-2xl">
      <h2 className="text-2xl font-bold flex items-center gap-2">
        <Settings className="h-6 w-6" /> Settings
      </h2>

      {/* Risk Management */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Shield className="h-5 w-5" /> Risk Management
          </CardTitle>
          <CardDescription>Configure risk limits for trading</CardDescription>
        </CardHeader>
        <CardContent className="space-y-1">
          <SettingRow
            label="Max Single Bet"
            description="Maximum percentage of total balance per trade"
            defaultValue="10"
            unit="%"
          />
          <Separator />
          <SettingRow
            label="Max Daily Loss"
            description="Stop trading when daily loss exceeds this percentage"
            defaultValue="5"
            unit="%"
          />
          <Separator />
          <SettingRow
            label="Max Position Concentration"
            description="Maximum exposure to a single market"
            defaultValue="20"
            unit="%"
          />
          <Separator />
          <SettingRow
            label="Min Edge"
            description="Minimum edge percentage for arbitrage signals"
            defaultValue="1.0"
            unit="%"
          />
          <Separator />
          <SettingRow
            label="Max Positions"
            description="Maximum number of simultaneous open positions"
            defaultValue="10"
          />
          <Separator />
          <SettingRow
            label="Expiry Buffer"
            description="Don't open new positions within this many hours of market expiry"
            defaultValue="24"
            unit="hrs"
          />
          <div className="pt-4 flex justify-end">
            <Button>Save Risk Settings</Button>
          </div>
        </CardContent>
      </Card>

      {/* API Keys */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Key className="h-5 w-5" /> API Configuration
          </CardTitle>
          <CardDescription>Polymarket API credentials (stored in .env)</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium">API Key</label>
            <Input type="password" placeholder="Enter your Polymarket API key" className="mt-1" />
          </div>
          <div>
            <label className="text-sm font-medium">API Secret</label>
            <Input type="password" placeholder="Enter your Polymarket API secret" className="mt-1" />
          </div>
          <div>
            <label className="text-sm font-medium">Private Key</label>
            <Input type="password" placeholder="Enter your wallet private key" className="mt-1" />
          </div>
          <p className="text-xs text-muted-foreground">
            Credentials are stored locally in your .env file and never transmitted.
          </p>
          <div className="flex justify-end">
            <Button>Save API Settings</Button>
          </div>
        </CardContent>
      </Card>

      {/* Notifications */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Bell className="h-5 w-5" /> Notifications
          </CardTitle>
          <CardDescription>Configure Telegram notifications (optional)</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium">Telegram Bot Token</label>
            <Input placeholder="Enter your Telegram bot token" className="mt-1" />
          </div>
          <div>
            <label className="text-sm font-medium">Telegram Chat ID</label>
            <Input placeholder="Enter your Telegram chat ID" className="mt-1" />
          </div>
          <div className="flex justify-end">
            <Button variant="outline">Test Notification</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
