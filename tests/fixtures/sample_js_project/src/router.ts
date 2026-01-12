/** Router module. */
import { Handler } from "./handlers";

export class Router {
  private handlers: Handler[];

  constructor() {
    this.handlers = [];
  }

  registerRoutes(): void {
    console.log("Routes registered");
  }

  addHandler(handler: Handler): void {
    this.handlers.push(handler);
  }
}
