/** Application class. */
import { Router } from "./router";
import { Logger } from "./utils/logger";

export class App {
  private router: Router;
  private logger: Logger;

  constructor(private config: any) {
    this.logger = new Logger();
    this.router = new Router();
  }

  start(): void {
    this.logger.info("Starting application");
    this.router.registerRoutes();
  }
}
