package com.bencodez.mysqldriver.spigot;

import org.bukkit.plugin.java.JavaPlugin;

public final class DriverPluginSpigot extends JavaPlugin {

	@Override
	public void onEnable() {
	}

	@Override
	public void onDisable() {
		// Nothing needed: we don't deregister drivers because other plugins may be using them.
	}
}
