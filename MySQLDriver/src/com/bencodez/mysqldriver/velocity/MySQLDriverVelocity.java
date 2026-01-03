package com.bencodez.mysqldriver.velocity;

import java.util.logging.Logger;

import com.google.inject.Inject;
import com.velocitypowered.api.event.Subscribe;
import com.velocitypowered.api.event.proxy.ProxyInitializeEvent;
import com.velocitypowered.api.plugin.Plugin;
import com.velocitypowered.api.proxy.ProxyServer;

@Plugin(id = "mysqldriver", name = "MySQLDriver", version = "1.0", description = "Plugin containg mysql driver for velocity", authors = {
		"BenCodez" })
public class MySQLDriverVelocity {
	@SuppressWarnings("unused")
	private final ProxyServer server;
	@SuppressWarnings("unused")
	private final Logger logger;

	@Inject
	public MySQLDriverVelocity(ProxyServer server, Logger logger) {
		this.server = server;
		this.logger = logger;
	}

	@Subscribe
	public void onProxyInitialization(ProxyInitializeEvent event) {
		// to add metrics
	}
}
